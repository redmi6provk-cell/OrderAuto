import { Play, Users, Package, Settings, Clock, AlertTriangle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface AutomationStatsProps {
    stats: {
        total_accounts: number;
        active_accounts: number;
        total_products: number;
        active_products: number;
    };
    batchSize: number;
    accountSelectionMode: 'range' | 'custom';
    accountRangeStart: number;
    accountRangeEnd: number;
    customAccountEmails: string;
}

export function AutomationStats({
    stats,
    batchSize,
    accountSelectionMode,
    accountRangeStart,
    accountRangeEnd,
    customAccountEmails
}: AutomationStatsProps) {
    const customEmailCount = customAccountEmails
        .split(',')
        .map(email => email.trim())
        .filter(email => email !== '').length;

    return (
        <div className="space-y-6">
            {/* Header Section */}
            <div className="bg-white rounded-xl border border-secondary-300 p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center">
                    <div className="flex items-center justify-center w-12 h-12 bg-primary-100 rounded-xl mr-4 shadow-sm">
                        <Play className="h-6 w-6 text-primary-600" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-secondary-900 tracking-tight">Automation Control</h1>
                        <p className="text-sm text-secondary-500">Manage bulk Flipkart automation with parallel browser sessions</p>
                    </div>
                </div>
                <div className="flex items-center px-4 py-2 bg-success-50 rounded-full border border-success-200 shadow-sm">
                    <div className="w-2.5 h-2.5 bg-success-500 rounded-full mr-2 animate-pulse"></div>
                    <span className="text-sm font-medium text-success-700">System Ready</span>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <Card className="border border-secondary-300 shadow-premium hover:shadow-premium-md transition-all duration-300">
                    <CardContent className="p-6 flex items-center space-x-4">
                        <div className="flex items-center justify-center w-12 h-12 bg-primary-50 rounded-xl text-primary-600">
                            <Users className="h-6 w-6" />
                        </div>
                        <div>
                            <p className="text-sm font-medium text-secondary-500">Flipkart Accounts</p>
                            <div className="flex items-baseline gap-1">
                                <p className="text-2xl font-bold text-secondary-900">{stats.active_accounts}</p>
                                <span className="text-sm text-secondary-400">/ {stats.total_accounts}</span>
                            </div>
                            <p className="text-xs text-primary-600 font-medium">Active accounts</p>
                        </div>
                    </CardContent>
                </Card>

                <Card className="border border-secondary-300 shadow-premium hover:shadow-premium-md transition-all duration-300">
                    <CardContent className="p-6 flex items-center space-x-4">
                        <div className="flex items-center justify-center w-12 h-12 bg-success-50 rounded-xl text-success-600">
                            <Package className="h-6 w-6" />
                        </div>
                        <div>
                            <p className="text-sm font-medium text-secondary-500">Products</p>
                            <div className="flex items-baseline gap-1">
                                <p className="text-2xl font-bold text-secondary-900">{stats.active_products}</p>
                                <span className="text-sm text-secondary-400">/ {stats.total_products}</span>
                            </div>
                            <p className="text-xs text-success-600 font-medium">Active products</p>
                        </div>
                    </CardContent>
                </Card>

                <Card className="border border-secondary-300 shadow-premium hover:shadow-premium-md transition-all duration-300">
                    <CardContent className="p-6 flex items-center space-x-4">
                        <div className="flex items-center justify-center w-12 h-12 bg-purple-50 rounded-xl text-purple-600">
                            <Settings className="h-6 w-6" />
                        </div>
                        <div>
                            <p className="text-sm font-medium text-secondary-500">Batch Size</p>
                            <p className="text-2xl font-bold text-secondary-900">{batchSize}</p>
                            <p className="text-xs text-purple-600 font-medium">Parallel browsers</p>
                        </div>
                    </CardContent>
                </Card>

                <Card className="border-none shadow-premium hover:shadow-premium-md transition-all duration-300">
                    <CardContent className="p-6 flex items-center space-x-4">
                        <div className="flex items-center justify-center w-12 h-12 bg-orange-50 rounded-xl text-orange-600">
                            <Clock className="h-6 w-6" />
                        </div>
                        <div>
                            <p className="text-sm font-medium text-secondary-500">Selection Mode</p>
                            {accountSelectionMode === 'range' ? (
                                <>
                                    <p className="text-2xl font-bold text-secondary-900">{accountRangeStart}-{accountRangeEnd}</p>
                                    <p className="text-xs text-orange-600 font-medium">Range ({accountRangeEnd - accountRangeStart + 1})</p>
                                </>
                            ) : (
                                <>
                                    <p className="text-2xl font-bold text-secondary-900">{customEmailCount}</p>
                                    <p className="text-xs text-orange-600 font-medium">Custom emails</p>
                                </>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Warning for Setup */}
            {(stats.active_accounts === 0 || stats.active_products === 0) && (
                <div className="p-4 bg-warning-50 border border-warning-300 rounded-xl flex items-start gap-3 animate-fade-in">
                    <AlertTriangle className="h-5 w-5 text-warning-600 mt-0.5 flex-shrink-0" />
                    <div>
                        <h4 className="text-sm font-semibold text-warning-800">Setup Required</h4>
                        <p className="text-sm text-warning-700 mt-1">
                            {stats.active_accounts === 0 && "No active Flipkart accounts found. "}
                            {stats.active_products === 0 && "No active products found. "}
                            Please configure accounts and products before starting automation.
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
