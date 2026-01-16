import { Settings, Play, LogIn, Loader } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

interface AutomationConfigProps {
    batchSize: number;
    setBatchSize: (val: number) => void;
    accountSelectionMode: 'range' | 'custom';
    setAccountSelectionMode: (val: 'range' | 'custom') => void;
    headless: boolean;
    setHeadless: (val: boolean) => void;
    accountRangeStart: number;
    setAccountRangeStart: (val: number) => void;
    accountRangeEnd: number;
    setAccountRangeEnd: (val: number) => void;
    customAccountEmails: string;
    setCustomAccountEmails: (val: string) => void;
    automationType: string;
    setAutomationType: (val: string) => void;
    selectedAddressId: number | null;
    setSelectedAddressId: (val: number | null) => void;
    addresses: any[];
    maxCartValue: number | '';
    setMaxCartValue: (val: number | '') => void;
    viewMode: string;
    setViewMode: (val: string) => void;
    couponCode: string;
    setCouponCode: (val: string) => void;
    couponCodesText: string;
    setCouponCodesText: (val: string) => void;
    gstin: string;
    setGstin: (val: string) => void;
    businessName: string;
    setBusinessName: (val: string) => void;
    stealDealProduct: string;
    setStealDealProduct: (val: string) => void;
    automationRunning: boolean;
    startAutomation: () => void;
    startLoginTest: () => void;
    activeAccountsCount: number;
}

export function AutomationConfig({
    batchSize, setBatchSize,
    accountSelectionMode, setAccountSelectionMode,
    headless, setHeadless,
    accountRangeStart, setAccountRangeStart,
    accountRangeEnd, setAccountRangeEnd,
    customAccountEmails, setCustomAccountEmails,
    automationType, setAutomationType,
    selectedAddressId, setSelectedAddressId,
    addresses,
    maxCartValue, setMaxCartValue,
    viewMode, setViewMode,
    couponCode, setCouponCode,
    couponCodesText, setCouponCodesText,
    gstin, setGstin,
    businessName, setBusinessName,
    stealDealProduct, setStealDealProduct,
    automationRunning,
    startAutomation,
    startLoginTest,
    activeAccountsCount
}: AutomationConfigProps) {

    const estimatedBatches = accountSelectionMode === 'range'
        ? Math.ceil((accountRangeEnd - accountRangeStart + 1) / batchSize)
        : Math.ceil(customAccountEmails.split(',').map(e => e.trim()).filter(e => e !== '').length / batchSize);

    const totalAccounts = accountSelectionMode === 'range'
        ? (accountRangeEnd - accountRangeStart + 1)
        : customAccountEmails.split(',').map(e => e.trim()).filter(e => e !== '').length;

    // List of types that force Desktop mode
    const desktopRequiredTypes = ['full_automation', 'add_address', 'add_coupon', 'remove_addresses', 'clear_cart'];
    const isDesktopRequired = desktopRequiredTypes.includes(automationType);

    return (
        <Card className="border-none shadow-premium">
            <CardHeader className="border-b border-secondary-100 bg-secondary-50/30">
                <CardTitle className="flex items-center text-xl text-secondary-900">
                    <Settings className="mr-2 h-5 w-5 text-primary-600" />
                    Configuration
                </CardTitle>
                <CardDescription>Configure your automation settings step by step</CardDescription>
            </CardHeader>
            <CardContent className="space-y-8 p-6">

                {/* Step 1: Basic Settings */}
                <div>
                    <h3 className="text-sm font-semibold text-secondary-900 uppercase tracking-wider mb-4 flex items-center">
                        <span className="bg-secondary-100 text-secondary-600 w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2">1</span>
                        Basic Settings
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="space-y-2">
                            <Label>Batch Size</Label>
                            <select
                                value={batchSize}
                                onChange={(e) => setBatchSize(Number(e.target.value))}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {[1, 2, 3, 4, 5].map(size => (
                                    <option key={size} value={size}>{size} Browser{size > 1 ? 's' : ''}</option>
                                ))}
                            </select>
                            <p className="text-xs text-secondary-500">Parallel Chromium instances (1-5)</p>
                        </div>

                        <div className="space-y-2">
                            <Label>Account Selection</Label>
                            <select
                                value={accountSelectionMode}
                                onChange={(e) => setAccountSelectionMode(e.target.value as 'range' | 'custom')}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <option value="range">Range Based</option>
                                <option value="custom">Custom Emails</option>
                            </select>
                            <p className="text-xs text-secondary-500">How to select accounts</p>
                        </div>

                        <div className="space-y-2">
                            <Label>Headless Mode</Label>
                            <div className="flex items-center h-10">
                                <label className="flex items-center cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={headless}
                                        onChange={(e) => setHeadless(e.target.checked)}
                                        className="sr-only peer"
                                    />
                                    <div className="relative w-11 h-6 bg-secondary-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                                    <span className="ms-3 text-sm font-medium text-secondary-700">{headless ? 'Enabled (Faster)' : 'Disabled (Visible)'}</span>
                                </label>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="h-px bg-secondary-100" />

                {/* Step 2: Account Selection */}
                <div>
                    <h3 className="text-sm font-semibold text-secondary-900 uppercase tracking-wider mb-4 flex items-center">
                        <span className="bg-secondary-100 text-secondary-600 w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2">2</span>
                        Target Accounts
                    </h3>

                    {accountSelectionMode === 'range' ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <Label>Start Account #</Label>
                                <Input
                                    type="number"
                                    value={accountRangeStart}
                                    onChange={(e) => {
                                        const value = e.currentTarget.value === '' ? NaN : Number(e.currentTarget.value);
                                        setAccountRangeStart(Number.isNaN(value) ? 0 : value);
                                    }}
                                />
                            </div>

                            <div className="space-y-2">
                                <Label>End Account #</Label>
                                <Input
                                    type="number"
                                    value={accountRangeEnd}
                                    onChange={(e) => {
                                        const value = e.currentTarget.value === '' ? NaN : Number(e.currentTarget.value);
                                        setAccountRangeEnd(Number.isNaN(value) ? 0 : value);
                                    }}
                                />
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <Label>Custom Emails</Label>
                            <Textarea
                                value={customAccountEmails}
                                onChange={(e) => setCustomAccountEmails(e.target.value)}
                                placeholder="user1@example.com, user2@example.com"
                                rows={4}
                                className="font-mono text-sm"
                            />
                            <p className="text-xs text-secondary-500">Comma-separated list of registered emails.</p>
                        </div>
                    )}
                </div>

                <div className="h-px bg-secondary-100" />

                {/* Step 3: Action Settings */}
                <div>
                    <h3 className="text-sm font-semibold text-secondary-900 uppercase tracking-wider mb-4 flex items-center">
                        <span className="bg-secondary-100 text-secondary-600 w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2">3</span>
                        Action Settings
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <Label>Automation Type</Label>
                            <select
                                value={automationType}
                                onChange={(e) => setAutomationType(e.target.value)}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <option value="login_test">Login Test Only</option>
                                <option value="full_automation">Full Automation (Order)</option>
                                <option value="add_address">Add New Address</option>
                                <option value="add_coupon">Add Coupon</option>
                                <option value="remove_addresses">Remove All Addresses</option>
                                <option value="clear_cart">Clear Grocery Cart</option>
                            </select>
                        </div>

                        <div className="space-y-2">
                            <Label>Delivery Address</Label>
                            <select
                                value={selectedAddressId || ''}
                                onChange={(e) => setSelectedAddressId(e.target.value ? Number(e.target.value) : null)}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <option value="">Select Address Template</option>
                                {addresses.map(address => (
                                    <option key={address.id} value={address.id}>
                                        {address.name} {address.is_default ? '(Default)' : ''}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                        <div className="space-y-2">
                            <Label>Max Cart Value (₹)</Label>
                            <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={maxCartValue}
                                onChange={(e) => setMaxCartValue(e.target.value === '' ? '' : Number(e.target.value))}
                                placeholder="Optional limit"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Browser View Mode</Label>
                            <div className="flex items-center h-10 gap-6">
                                <label className="flex items-center gap-2 cursor-pointer group">
                                    <input
                                        type="radio"
                                        name="viewMode"
                                        value="desktop"
                                        checked={viewMode === 'desktop'}
                                        onChange={() => setViewMode('desktop')}
                                        className="w-4 h-4 text-primary-600 border-gray-300 focus:ring-primary-500"
                                    />
                                    <span className="text-sm font-medium text-secondary-700 group-hover:text-primary-600">
                                        Desktop
                                    </span>
                                </label>

                                <label className={`flex items-center gap-2 cursor-pointer group ${isDesktopRequired ? 'opacity-50 cursor-not-allowed' : ''}`}>
                                    <input
                                        type="radio"
                                        name="viewMode1"
                                        value="mobile"
                                        checked={viewMode === 'mobile'}
                                        onChange={() => setViewMode('mobile')}
                                        
                                        className="w-4 h-4 text-primary-600 border-gray-300 focus:ring-primary-500"
                                    />
                                    <span className="text-sm font-medium text-secondary-700 group-hover:text-primary-600">
                                        Mobile
                                    </span>
                                </label>

                                
                            </div>
                        </div>
                    </div>

                    {/* Dynamic Fields */}
                    {automationType === 'add_coupon' && (
                        <div className="mt-6 p-4 bg-secondary-50 rounded-lg border border-secondary-200 animate-fade-in">
                            {accountSelectionMode === 'custom' ? (
                                <div className="space-y-2">
                                    <Label>Coupon Codes (1 per email)</Label>
                                    <Textarea
                                        value={couponCodesText}
                                        onChange={(e) => setCouponCodesText(e.target.value)}
                                        placeholder="Enter one code per email (comma or newline separated)"
                                        className="h-28 font-mono text-sm"
                                    />
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    <Label>Coupon Code</Label>
                                    <Input
                                        type="text"
                                        value={couponCode}
                                        onChange={(e) => setCouponCode(e.target.value)}
                                        placeholder="Enter single coupon code"
                                    />
                                </div>
                            )}
                        </div>
                    )}

                    {automationType === 'full_automation' && (
                        <div className="mt-6 p-4 bg-secondary-50 rounded-lg border border-secondary-200 animate-fade-in space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>GSTIN (Optional)</Label>
                                    <Input
                                        type="text"
                                        value={gstin}
                                        onChange={(e) => setGstin(e.target.value)}
                                        placeholder="15-character GSTIN"
                                        className="font-mono"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Business Name (Optional)</Label>
                                    <Input
                                        type="text"
                                        value={businessName}
                                        onChange={(e) => setBusinessName(e.target.value)}
                                        placeholder="Registered business name"
                                    />
                                </div>
                            </div>
                            <div className="space-y-2">
                                <Label>Steal Deal Product (Optional)</Label>
                                <Input
                                    type="text"
                                    value={stealDealProduct}
                                    onChange={(e) => setStealDealProduct(e.target.value)}
                                    placeholder="e.g., Tide Double Power"
                                />
                            </div>
                        </div>
                    )}
                </div>

                <div className="h-px bg-secondary-100" />

                {/* Step 4: Summary & Buttons */}
                <div>
                    <div className="bg-primary-50/50 border border-primary-100 rounded-xl p-5 mb-6">
                        <h4 className="font-semibold text-primary-900 mb-3 text-sm uppercase tracking-wide">Summary</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-y-2 gap-x-8 text-sm">
                            <div className="flex justify-between">
                                <span className="text-secondary-500">Browsers:</span>
                                <span className="font-medium text-secondary-900">{batchSize} Parallel</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-secondary-500">Type:</span>
                                <span className="font-medium text-secondary-900 capitalize">{automationType.replace('_', ' ')}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-secondary-500">View Mode:</span>
                                <span className="font-medium text-secondary-900 capitalize">{viewMode}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-secondary-500">Total Accounts:</span>
                                <span className="font-medium text-secondary-900">{totalAccounts}</span>
                            </div>
                        </div>
                    </div>

                    <div className="flex flex-col sm:flex-row justify-center gap-4">
                        <Button
                            onClick={startAutomation}
                            disabled={automationRunning || activeAccountsCount === 0}
                            size="lg"
                            className="w-full sm:w-auto min-w-[200px] shadow-premium"
                        >
                            {automationRunning ? (
                                <><Loader className="mr-2 h-5 w-5 animate-spin" /> Running...</>
                            ) : (
                                <><Play className="mr-2 h-5 w-5" /> Start Automation</>
                            )}
                        </Button>

                        <Button
                            onClick={startLoginTest}
                            disabled={automationRunning || activeAccountsCount === 0}
                            variant="outline"
                            size="lg"
                            className="w-full sm:w-auto min-w-[200px]"
                        >
                            <LogIn className="mr-2 h-5 w-5" /> Test Login
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
