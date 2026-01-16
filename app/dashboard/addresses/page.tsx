'use client'

import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, MapPin, Phone, Mail, Star, Check } from 'lucide-react'
import { addressesService } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface Address {
  id: number
  name: string
  description?: string
  address_template: string
  office_no_min: number
  office_no_max: number
  name_postfix: string
  phone_prefix: string
  pincode: string
  is_active: boolean
  is_default: boolean
  created_at: string
}

interface AddressFormData {
  name: string
  description: string
  address_template: string
  office_no_min: number
  office_no_max: number
  name_postfix: string
  phone_prefix: string
  pincode: string
}

export default function AddressesPage() {
  const [addresses, setAddresses] = useState<Address[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingAddress, setEditingAddress] = useState<Address | null>(null)
  const [formData, setFormData] = useState<AddressFormData>({
    name: '',
    description: '',
    address_template: '',
    office_no_min: 100,
    office_no_max: 999,
    name_postfix: 'Shivshakti',
    phone_prefix: '6000',
    pincode: '400010'
  })

  useEffect(() => {
    fetchAddresses()
  }, [])

  const fetchAddresses = async () => {
    try {
      const data = await addressesService.getAddresses()
      setAddresses(data)
    } catch (error) {
      console.error('Failed to fetch addresses:', error)
    } finally {
      setLoading(false)
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editingAddress) {
        await addressesService.updateAddress(editingAddress.id, formData)
      } else {
        await addressesService.createAddress(formData)
      }
      await fetchAddresses()
      resetForm()
    } catch (error) {
      console.error('Failed to save address:', error)
    }
  }

  const handleDelete = async (id: number) => {
    if (confirm('Are you sure you want to delete this address?')) {
      try {
        await addressesService.deleteAddress(id)
        await fetchAddresses()
      } catch (error) {
        console.error('Failed to delete address:', error)
      }
    }
  }

  const handleSetDefault = async (id: number) => {
    try {
      await addressesService.setDefaultAddress(id)
      await fetchAddresses()
    } catch (error) {
      console.error('Failed to set default address:', error)
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      address_template: '',
      office_no_min: 100,
      office_no_max: 999,
      name_postfix: 'Shivshakti',
      phone_prefix: '6000',
      pincode: '400010'
    })
    setEditingAddress(null)
    setShowForm(false)
  }

  const startEdit = (address: Address) => {
    setFormData({
      name: address.name,
      description: address.description || '',
      address_template: address.address_template,
      office_no_min: address.office_no_min,
      office_no_max: address.office_no_max,
      name_postfix: address.name_postfix,
      phone_prefix: address.phone_prefix,
      pincode: address.pincode
    })
    setEditingAddress(address)
    setShowForm(true)
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="loading-spinner h-12 w-12 border-4 border-primary-200 border-t-primary-600 rounded-full"></div>
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-secondary-900 tracking-tight">Address Management</h1>
          <p className="text-secondary-500 mt-1">
            Manage delivery addresses for automation orders
          </p>
        </div>
        <Button
          onClick={() => setShowForm(true)}
          className="gap-2 shadow-premium-sm hover:shadow-premium"
        >
          <Plus className="h-4 w-4" />
          Add Address
        </Button>
      </div>

      {/* Address Form */}
      {showForm && (
        <Card className="animate-slide-down border-primary-100 shadow-premium-md">
          <CardHeader>
            <CardTitle>{editingAddress ? 'Edit Address' : 'Add New Address'}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Address Name</Label>
                  <Input
                    id="name"
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., Office Address"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Input
                    id="description"
                    type="text"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Optional description"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="address_template">Address Template</Label>
                <Textarea
                  id="address_template"
                  required
                  rows={3}
                  value={formData.address_template}
                  onChange={(e) => setFormData({ ...formData, address_template: e.target.value })}
                  placeholder="Use {office_no} as placeholder for random office number"
                />
                <p className="text-xs text-secondary-500">
                  Use <code className="bg-secondary-100 px-1 rounded text-secondary-700">{'{office_no}'}</code> as a placeholder for the random office number.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label htmlFor="office_no_min">Minimum Office Number</Label>
                  <Input
                    id="office_no_min"
                    type="number"
                    required
                    value={formData.office_no_min}
                    onChange={(e) => setFormData({ ...formData, office_no_min: parseInt(e.target.value) || 100 })}
                    min="1"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="office_no_max">Maximum Office Number</Label>
                  <Input
                    id="office_no_max"
                    type="number"
                    required
                    value={formData.office_no_max}
                    onChange={(e) => setFormData({ ...formData, office_no_max: parseInt(e.target.value) || 999 })}
                    min="1"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label htmlFor="name_postfix">Name Postfix</Label>
                  <Input
                    id="name_postfix"
                    type="text"
                    required
                    value={formData.name_postfix}
                    onChange={(e) => setFormData({ ...formData, name_postfix: e.target.value })}
                    placeholder="Shivshakti"
                  />
                  <p className="text-xs text-secondary-500">
                    Appended to random names (e.g., "Aarav Shivshakti")
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="phone_prefix">Phone Prefix</Label>
                  <Input
                    id="phone_prefix"
                    type="text"
                    required
                    value={formData.phone_prefix}
                    onChange={(e) => setFormData({ ...formData, phone_prefix: e.target.value })}
                    placeholder="6000"
                  />
                  <p className="text-xs text-secondary-500">
                    First 4 digits of phone numbers (e.g., "6000...")
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="pincode">Default Pincode</Label>
                <Input
                  id="pincode"
                  type="text"
                  required
                  value={formData.pincode}
                  onChange={(e) => setFormData({ ...formData, pincode: e.target.value })}
                  placeholder="400010"
                />
                <p className="text-xs text-secondary-500">
                  Default pincode for delivery location selection
                </p>
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={resetForm}
                >
                  Cancel
                </Button>
                <Button type="submit">
                  {editingAddress ? 'Update Address' : 'Create Address'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Addresses List */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {addresses.map((address) => (
          <Card key={address.id} className={`transition-all duration-300 hover:shadow-premium-md group ${address.is_default ? 'border-primary-200 bg-primary-50/30' : ''}`}>
            <CardContent className="p-6">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-2">
                  <div className={`p-2 rounded-lg ${address.is_default ? 'bg-primary-100 text-primary-600' : 'bg-secondary-100 text-secondary-500'}`}>
                    <MapPin className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-secondary-900">{address.name}</h3>
                    {address.is_default && (
                      <span className="text-xs font-medium text-primary-600 flex items-center gap-1">
                        <Star className="h-3 w-3 fill-current" /> Default
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {!address.is_default && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleSetDefault(address.id)}
                      title="Set as default"
                      className="h-8 w-8 text-secondary-400 hover:text-primary-600"
                    >
                      <Star className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => startEdit(address)}
                    className="h-8 w-8 text-secondary-400 hover:text-primary-600"
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(address.id)}
                    className="h-8 w-8 text-secondary-400 hover:text-danger-600"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="space-y-3 text-sm">
                <div className="bg-white p-3 rounded-md border border-secondary-100 text-secondary-600 font-mono text-xs break-words">
                  {address.address_template}
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="flex flex-col">
                    <span className="text-xs text-secondary-400">Phone Prefix</span>
                    <span className="font-medium text-secondary-700">{address.phone_prefix}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs text-secondary-400">Pincode</span>
                    <span className="font-medium text-secondary-700">{address.pincode}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs text-secondary-400">Office Range</span>
                    <span className="font-medium text-secondary-700">{address.office_no_min} - {address.office_no_max}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs text-secondary-400">Name Postfix</span>
                    <span className="font-medium text-secondary-700">{address.name_postfix}</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {/* Add New Card Button */}
        <button
          onClick={() => setShowForm(true)}
          className="flex flex-col items-center justify-center p-6 rounded-xl border-2 border-dashed border-secondary-200 hover:border-primary-300 hover:bg-primary-50/30 transition-all duration-300 group min-h-[300px]"
        >
          <div className="h-12 w-12 rounded-full bg-secondary-100 group-hover:bg-primary-100 flex items-center justify-center mb-3 transition-colors">
            <Plus className="h-6 w-6 text-secondary-400 group-hover:text-primary-600" />
          </div>
          <span className="font-medium text-secondary-600 group-hover:text-primary-700">Add New Address</span>
        </button>
      </div>

      {addresses.length === 0 && !showForm && (
        <div className="text-center py-16 bg-secondary-50/30 rounded-xl border border-dashed border-secondary-200">
          <MapPin className="mx-auto h-12 w-12 text-secondary-300 mb-4" />
          <h3 className="text-lg font-medium text-secondary-900">No addresses found</h3>
          <p className="text-secondary-500 mt-1 mb-6">
            Get started by creating a new address configuration.
          </p>
          <Button onClick={() => setShowForm(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Address
          </Button>
        </div>
      )}
    </div>
  )
}
