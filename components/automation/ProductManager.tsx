import { Plus, Trash2, Loader, ExternalLink, Package } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface Product {
    id: number;
    product_link: string;
    product_name: string | null;
    quantity: number;
}

interface NewProduct {
    product_name: string;
    product_link: string;
    quantity: number;
}

interface ProductManagerProps {
    products: Product[];
    newProducts: NewProduct[];
    setNewProducts: (products: NewProduct[]) => void;
    savingProducts: boolean;
    handleAddProduct: () => void;
    handleProductChange: (index: number, field: keyof NewProduct, value: string | number) => void;
    handleRemoveProduct: (index: number) => void;
    handleSaveProducts: () => void;
    handleDeleteProduct: (id: number) => void;
}

export function ProductManager({
    products,
    newProducts,
    setNewProducts,
    savingProducts,
    handleAddProduct,
    handleProductChange,
    handleRemoveProduct,
    handleSaveProducts,
    handleDeleteProduct
}: ProductManagerProps) {
    return (
        <Card className="border border-secondary-300 shadow-premium overflow-hidden">
            <CardHeader className="border-b border-secondary-100 bg-secondary-50/30">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center text-xl text-secondary-900">
                            <Package className="mr-2 h-5 w-5 text-primary-600" />
                            Product Management
                        </CardTitle>
                        <CardDescription>Manage products to be ordered during automation</CardDescription>
                    </div>
                    <div className="bg-primary-100 text-primary-700 text-xs font-medium px-2.5 py-1 rounded-full">
                        {products.length} Active
                    </div>
                </div>
            </CardHeader>
            <CardContent className="p-6 space-y-8">

                {/* Existing Products Table */}
                {products.length > 0 ? (
                    <div className="rounded-lg border border-secondary-200 overflow-hidden">
                        <table className="min-w-full divide-y divide-secondary-200">
                            <thead className="bg-secondary-50">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Product Name</th>
                                    <th className="px-6 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">URL</th>
                                    <th className="px-6 py-3 text-center text-xs font-semibold text-secondary-500 uppercase tracking-wider">Qty</th>
                                    <th className="px-6 py-3 text-right text-xs font-semibold text-secondary-500 uppercase tracking-wider">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-secondary-100">
                                {products.map(product => (
                                    <tr key={product.id} className="hover:bg-secondary-50/50 transition-colors group">
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-secondary-900">
                                            {product.product_name || <span className="text-secondary-400 italic">Unnamed Product</span>}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary-500 max-w-xs truncate">
                                            <a
                                                href={product.product_link}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-primary-600 hover:text-primary-700 hover:underline flex items-center gap-1"
                                            >
                                                <span className="truncate">{product.product_link}</span>
                                                <ExternalLink className="h-3 w-3 flex-shrink-0" />
                                            </a>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary-600 text-center font-mono">
                                            {product.quantity}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => handleDeleteProduct(product.id)}
                                                className="text-secondary-400 hover:text-danger-600 hover:bg-danger-50 opacity-0 group-hover:opacity-100 transition-all"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="text-center py-12 bg-secondary-50/30 rounded-xl border border-dashed border-secondary-200">
                        <Package className="mx-auto h-12 w-12 text-secondary-300 mb-3" />
                        <h3 className="text-lg font-medium text-secondary-900">No products added</h3>
                        <p className="text-secondary-500 text-sm">Add products below to get started with automation.</p>
                    </div>
                )}

                <div className="h-px bg-secondary-100" />

                {/* Add New Products Form */}
                <div>
                    <h4 className="text-sm font-semibold text-secondary-900 uppercase tracking-wider mb-4">Add New Products</h4>
                    <div className="space-y-4">
                        {newProducts.map((product, index) => (
                            <div key={index} className="flex flex-col sm:flex-row gap-4 items-start sm:items-end bg-secondary-50/50 p-4 rounded-lg border border-secondary-100 hover:border-primary-100 transition-colors">
                                <div className="flex-1 w-full sm:w-auto space-y-1.5">
                                    <Label className="text-xs">Product Name</Label>
                                    <Input
                                        type="text"
                                        value={product.product_name}
                                        onChange={(e) => handleProductChange(index, 'product_name', e.target.value)}
                                        placeholder="e.g. Acer Laptop"
                                        className="bg-white"
                                    />
                                </div>
                                <div className="flex-[2] w-full sm:w-auto space-y-1.5">
                                    <Label className="text-xs">Product URL</Label>
                                    <Input
                                        type="url"
                                        value={product.product_link}
                                        onChange={(e) => handleProductChange(index, 'product_link', e.target.value)}
                                        placeholder="https://flipkart.com/product/..."
                                        className="bg-white"
                                    />
                                </div>
                                <div className="w-24 space-y-1.5">
                                    <Label className="text-xs">Quantity</Label>
                                    <Input
                                        type="number"
                                        min="1"
                                        value={product.quantity}
                                        onChange={(e) => handleProductChange(index, 'quantity', parseInt(e.target.value) || 1)}
                                        className="bg-white text-center"
                                    />
                                </div>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleRemoveProduct(index)}
                                    disabled={newProducts.length === 1}
                                    className="text-secondary-400 hover:text-danger-600 hover:bg-danger-50 mb-[2px]"
                                >
                                    <Trash2 className="h-5 w-5" />
                                </Button>
                            </div>
                        ))}
                    </div>

                    <div className="mt-6 flex flex-wrap gap-3">
                        <Button onClick={handleAddProduct} variant="outline" className="gap-2 border-dashed border-secondary-300 hover:border-primary-500 hover:bg-primary-50 text-secondary-600 hover:text-primary-700">
                            <Plus className="h-4 w-4" />
                            Add Another Row
                        </Button>
                        <div className="flex-1" />
                        <Button
                            onClick={handleSaveProducts}
                            disabled={savingProducts}
                            className="gap-2 shadow-premium-sm hover:shadow-premium min-w-[140px]"
                        >
                            {savingProducts ? (
                                <>
                                    <Loader className="animate-spin h-4 w-4" />
                                    Saving...
                                </>
                            ) : (
                                'Save Products'
                            )}
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
