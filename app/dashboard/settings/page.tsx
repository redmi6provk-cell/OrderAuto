'use client'

import React, { useState, useEffect } from 'react'
import { api, settingsService } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { Save, Plus, Trash2, Upload, Download, X } from 'lucide-react'
import { toast } from 'sonner'

interface Setting {
  setting_key: string
  setting_value: string
  setting_type: string
  description: string
  updated_at: string
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Setting[]>([])
  const [names, setNames] = useState<string[]>([])
  const [newName, setNewName] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Settings form state - removed deprecated address fields

  useEffect(() => {
    loadSettings()
    loadNames()
  }, [])

  const loadSettings = async () => {
    try {
      const response = await settingsService.getAll()
      if (response.success) {
        const settingsData = response.settings
        setSettings(settingsData)

        // Populate form fields - address settings moved to addresses management
      }
    } catch (error) {
      console.error('Failed to load settings:', error)
      toast.error('Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  const loadNames = async () => {
    try {
      const response = await settingsService.getNames()
      if (response.success) {
        setNames(response.names)
      }
    } catch (error) {
      console.error('Failed to load names:', error)
      toast.error('Failed to load names')
    }
  }

  const saveSettings = async () => {
    setSaving(true)
    try {
      // Address settings have been moved to addresses management
      // Only general settings would be saved here if any exist
      toast.success('Settings saved successfully')
    } catch (error) {
      console.error('Failed to save settings:', error)
      toast.error('Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const saveNames = async () => {
    try {
      const response = await settingsService.updateNames(names)
      if (response.success) {
        toast.success('Names saved successfully')
      }
    } catch (error) {
      console.error('Failed to save names:', error)
      toast.error('Failed to save names')
    }
  }

  const addName = () => {
    if (newName.trim()) {
      // Check if the input contains commas (bulk add)
      if (newName.includes(',')) {
        // Split by comma, trim each name, filter out duplicates and empty strings
        const newNamesList = newName
          .split(',')
          .map(name => name.trim())
          .filter(name => name && !names.includes(name))

        if (newNamesList.length > 0) {
          setNames([...names, ...newNamesList])
          setNewName('')
          toast.success(`Added ${newNamesList.length} names successfully`)
        } else {
          toast.error('No new names to add (duplicates or empty names)')
        }
      } else {
        // Single name add
        if (!names.includes(newName.trim())) {
          setNames([...names, newName.trim()])
          setNewName('')
          toast.success('Name added successfully')
        } else {
          toast.error('Name already exists')
        }
      }
    }
  }

  const removeName = (index: number) => {
    setNames(names.filter((_, i) => i !== index))
  }

  const clearAllNames = async () => {
    if (confirm('Are you sure you want to clear all names? This action cannot be undone.')) {
      try {
        const response = await settingsService.clearNames()
        if (response.success) {
          setNames([])
          toast.success('All names cleared successfully')
        }
      } catch (error) {
        console.error('Failed to clear names:', error)
        toast.error('Failed to clear names')
      }
    }
  }

  const exportNames = () => {
    const blob = new Blob([names.join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'names.txt'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const importNames = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target?.result as string
        const importedNames = content.split('\n').map(name => name.trim()).filter(name => name)
        setNames([...new Set([...names, ...importedNames])]) // Remove duplicates
      }
      reader.readAsText(file)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="loading-spinner h-12 w-12 border-4 border-primary-200 border-t-primary-600 rounded-full"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage names for automation and other general settings. Address settings are now managed in the Addresses page.
        </p>
      </div>

      <div className="grid gap-6">
        {/* Info Card about Address Settings */}
        <Card>
          <CardHeader>
            <CardTitle>Address Settings</CardTitle>
            <CardDescription>
              Address settings have been moved to the dedicated Addresses page for better organization.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              You can now manage all address configurations, templates, and settings in the Addresses section.
            </p>
            <Button onClick={() => window.location.href = '/dashboard/addresses'} variant="outline">
              Go to Addresses Management
            </Button>
          </CardContent>
        </Card>

        {/* Names Management */}
        <Card>
          <CardHeader>
            <CardTitle>Name List Management</CardTitle>
            <CardDescription>
              Manage the list of names used for random generation. Names will be combined with the postfix above.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex gap-2">
                <Input
                  placeholder="Add names (e.g., 'Aarav' or 'Aarav, Vivaan, Aditya' for bulk add)..."
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && addName()}
                />
                <Button onClick={addName} size="sm">
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                💡 Tip: Use commas to add multiple names at once (e.g., "John, Jane, Bob")
              </p>
            </div>

            <div className="flex gap-2">
              <Button onClick={saveNames} size="sm">
                <Save className="mr-2 h-4 w-4" />
                Save Names
              </Button>
              <Button onClick={exportNames} variant="outline" size="sm">
                <Download className="mr-2 h-4 w-4" />
                Export
              </Button>
              <Button onClick={() => document.getElementById('importFile')?.click()} variant="outline" size="sm">
                <Upload className="mr-2 h-4 w-4" />
                Import
              </Button>
              <Button onClick={clearAllNames} variant="destructive" size="sm">
                <Trash2 className="mr-2 h-4 w-4" />
                Clear All
              </Button>
              <input
                id="importFile"
                type="file"
                accept=".txt"
                onChange={importNames}
                style={{ display: 'none' }}
              />
            </div>

            <div className="border rounded-lg p-4 max-h-60 overflow-y-auto">
              <div className="flex flex-wrap gap-2">
                {names.length === 0 ? (
                  <p className="text-muted-foreground">No names added yet.</p>
                ) : (
                  names.map((name, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-1 bg-muted px-2 py-1 rounded text-sm"
                    >
                      <span>{name}</span>
                      <button
                        onClick={() => removeName(index)}
                        className="text-muted-foreground hover:text-destructive ml-1"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            <p className="text-sm text-muted-foreground">
              Total names: {names.length}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
