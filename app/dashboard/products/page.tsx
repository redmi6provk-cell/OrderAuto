'use client';

import { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import { api } from '@/lib/api';
import { Package, Plus, Upload, Download, Trash2, Edit, ExternalLink, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface Product {
  id: number;
  product_link: string;
  product_name: string | null;
  quantity: number;
  is_active: boolean;
  created_at: string;
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // Form state
  const [formData, setFormData] = useState({
    product_link: '',
    product_name: '',
    quantity: 1
  });

  useEffect(() => {
    fetchProducts();
  }, []);

  // Normalize Flipkart URLs to ensure marketplace=GROCERY is present
  const normalizeFlipkartUrl = (rawUrl: string): string => {
    if (!rawUrl) return rawUrl;
    try {
      const url = new URL(rawUrl);
      const host = url.hostname.toLowerCase();
      if (!host.includes('flipkart.com')) return rawUrl; // Only normalize Flipkart URLs

      const params = url.searchParams;
      // If marketplace is missing or empty, set to GROCERY
      const marketplace = params.get('marketplace');
      if (!marketplace) {
        params.set('marketplace', 'GROCERY');
      }

      // Re-assign search in case params object is a live view
      url.search = params.toString();
      return url.toString();
    } catch {
      // If URL parsing fails, return original
      return rawUrl;
    }
  };

  const fetchProducts = async () => {
    try {
      const response = await api.get('/products/');
      setProducts(response.data);
    } catch (error) {
      toast.error('Failed to fetch products');
      console.error('Error fetching products:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const normalizedLink = normalizeFlipkartUrl(formData.product_link);
    const submitData = {
      ...formData,
      product_link: normalizedLink,
    };

    try {
      if (editingProduct) {
        // Update existing product
        const response = await api.put(`/products/${editingProduct.id}`, submitData);
        setProducts(products.map(p => p.id === editingProduct.id ? response.data : p));
        toast.success('Product updated successfully');
        setEditingProduct(null);
      } else {
        // Create new product
        const response = await api.post('/products/', submitData);
        setProducts([response.data, ...products]);
        toast.success('Product added successfully');
        setShowAddForm(false);
      }

      // Reset form
      setFormData({
        product_link: '',
        product_name: '',
        quantity: 1
      });
    } catch (error: any) {
      const errorDetail = error.response?.data?.detail;
      if (Array.isArray(errorDetail) && errorDetail.length > 0 && errorDetail[0].msg) {
        toast.error(errorDetail.map((e: any) => e.msg).join('; '));
      } else if (typeof errorDetail === 'string') {
        toast.error(errorDetail);
      } else {
        toast.error('Failed to save product');
      }
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this product?')) return;

    try {
      await api.delete(`/products/${id}`);
      setProducts(products.filter(p => p.id !== id));
      toast.success('Product deleted successfully');
    } catch (error) {
      toast.error('Failed to delete product');
    }
  };

  const handleEdit = (product: Product) => {
    setEditingProduct(product);
    setFormData({
      product_link: product.product_link,
      product_name: product.product_name || '',
      quantity: product.quantity
    });
    setShowAddForm(true);
  };

  const handleCsvImport = async () => {
    if (!csvFile) {
      toast.error('Please select a CSV file');
      return;
    }

    setImporting(true);
    const formData = new FormData();
    formData.append('file', csvFile);

    try {
      const response = await api.post('/products/import-csv', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      toast.success(response.data.message);

      if (response.data.errors && response.data.errors.length > 0) {
        console.log('Import errors:', response.data.errors);
        toast.error(`${response.data.error_count} errors occurred during import`);
      }

      setCsvFile(null);
      fetchProducts(); // Refresh the list
    } catch (error: any) {
      const errorDetail = error.response?.data?.detail;
      if (Array.isArray(errorDetail) && errorDetail.length > 0 && errorDetail[0].msg) {
        toast.error(errorDetail.map((e: any) => e.msg).join('; '));
      } else if (typeof errorDetail === 'string') {
        toast.error(errorDetail);
      } else {
        toast.error('Failed to import CSV');
      }
    } finally {
      setImporting(false);
    }
  };

  const downloadTemplate = async () => {
    try {
      const response = await api.get('/products/export-template', {
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'products_template.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      toast.success('Template downloaded successfully');
    } catch (error) {
      toast.error('Failed to download template');
    }
  };

  const toggleProductStatus = async (product: Product) => {
    try {
      const response = await api.put(`/products/${product.id}`, {
        is_active: !product.is_active
      });
      setProducts(products.map(p => p.id === product.id ? response.data : p));
      toast.success(`Product ${response.data.is_active ? 'activated' : 'deactivated'}`);
    } catch (error) {
      toast.error('Failed to update product status');
    }
  };

  const filteredProducts = products.filter(product =>
    product.product_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    product.product_link.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="loading-spinner h-12 w-12 border-4 border-primary-200 border-t-primary-600 rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-secondary-900 tracking-tight">Product Management</h1>
          <p className="text-secondary-500 mt-1">
            Manage Flipkart products for automated monitoring and ordering
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            onClick={downloadTemplate}
            className="gap-2"
          >
            <Download className="h-4 w-4" />
            Template
          </Button>
          <Button
            onClick={() => setShowAddForm(true)}
            className="gap-2 shadow-premium-sm hover:shadow-premium"
          >
            <Plus className="h-4 w-4" />
            Add Product
          </Button>
        </div>
      </div>

      {/* CSV Import Section */}
      <Card className="border-dashed border-2 border-secondary-200 bg-secondary-50/50">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row items-center gap-4">
            <div className="flex-1 w-full">
              <h3 className="text-lg font-medium text-secondary-900 mb-2 flex items-center gap-2">
                <Upload className="h-5 w-5 text-primary-600" />
                Import Products
              </h3>
              <p className="text-sm text-secondary-500 mb-4">
                Upload a CSV file with columns: product_link, quantity, product_name (optional)
              </p>
              <div className="flex gap-3">
                <Input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                  className="bg-white"
                />
                <Button
                  onClick={handleCsvImport}
                  disabled={!csvFile || importing}
                  variant="secondary"
                  className="min-w-[120px]"
                >
                  {importing ? (
                    <>
                      <div className="loading-spinner h-4 w-4 border-2 border-current border-t-transparent rounded-full mr-2"></div>
                      Importing
                    </>
                  ) : (
                    'Import CSV'
                  )}
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Add/Edit Product Form */}
      {showAddForm && (
        <Card className="animate-slide-down border-primary-100 shadow-premium-md">
          <CardHeader>
            <CardTitle>{editingProduct ? 'Edit Product' : 'Add New Product'}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="md:col-span-2 space-y-2">
                <Label htmlFor="product_link">Product Link *</Label>
                <Input
                  id="product_link"
                  type="url"
                  required
                  value={formData.product_link}
                  onChange={(e) => setFormData({ ...formData, product_link: e.target.value })}
                  onBlur={(e) => setFormData({ ...formData, product_link: normalizeFlipkartUrl(e.target.value) })}
                  placeholder="https://www.flipkart.com/product-link"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="product_name">Product Name (Optional)</Label>
                <Input
                  id="product_name"
                  type="text"
                  value={formData.product_name}
                  onChange={(e) => setFormData({ ...formData, product_name: e.target.value })}
                  placeholder="e.g. iPhone 15 Pro"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="quantity">Quantity *</Label>
                <Input
                  id="quantity"
                  type="number"
                  required
                  min="1"
                  value={formData.quantity}
                  onChange={(e) => setFormData({ ...formData, quantity: parseInt(e.target.value) })}
                />
              </div>

              <div className="md:col-span-2 flex justify-end gap-3 pt-4">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setShowAddForm(false);
                    setEditingProduct(null);
                    setFormData({
                      product_link: '',
                      product_name: '',
                      quantity: 1
                    });
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit">
                  {editingProduct ? 'Update Product' : 'Add Product'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Products List */}
      <Card className="overflow-hidden border-none shadow-premium">
        <div className="p-6 border-b border-secondary-100 bg-white flex flex-col sm:flex-row justify-between items-center gap-4">
          <h3 className="text-lg font-semibold text-secondary-900">
            All Products <span className="text-secondary-400 font-normal ml-1">({products.length})</span>
          </h3>
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-secondary-400" />
            <Input
              placeholder="Search products..."
              className="pl-9"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        {filteredProducts.length === 0 ? (
          <div className="text-center py-16 bg-secondary-50/30">
            <div className="bg-secondary-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
              <Package className="h-8 w-8 text-secondary-400" />
            </div>
            <h3 className="text-lg font-medium text-secondary-900">No products found</h3>
            <p className="text-secondary-500 mt-1 max-w-sm mx-auto">
              {searchTerm ? 'Try adjusting your search terms.' : 'Get started by adding a new product or importing from CSV.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-secondary-100 bg-secondary-50/50 text-xs uppercase tracking-wider text-secondary-500 font-medium">
                  <th className="px-6 py-4">Product Details</th>
                  <th className="px-6 py-4">Quantity</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-secondary-100 bg-white">
                {filteredProducts.map((product) => (
                  <tr key={product.id} className="group hover:bg-secondary-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-medium text-secondary-900 mb-1">
                          {product.product_name || 'Unnamed Product'}
                        </span>
                        <a
                          href={product.product_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1 w-fit"
                        >
                          View on Flipkart
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-secondary-600 font-medium">
                      {product.quantity} units
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => toggleProductStatus(product)}
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border transition-all ${product.is_active
                            ? 'bg-success-50 text-success-700 border-success-200 hover:bg-success-100'
                            : 'bg-secondary-100 text-secondary-600 border-secondary-200 hover:bg-secondary-200'
                          }`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${product.is_active ? 'bg-success-500' : 'bg-secondary-400'}`}></span>
                        {product.is_active ? 'Active' : 'Inactive'}
                      </button>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleEdit(product)}
                          className="h-8 w-8 text-secondary-500 hover:text-primary-600"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(product.id)}
                          className="h-8 w-8 text-secondary-500 hover:text-danger-600"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}



