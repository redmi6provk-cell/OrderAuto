import { X, Loader, Search, Download, CheckCircle, XCircle, BarChart3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

interface AccountStatRow {
    account: string;
    order_id?: string;
    expected_delivery?: string;
    basket_items?: number;
    cart_total?: number;
    address?: string;
    success?: boolean;
    message?: string;
}

interface SessionStatsProps {
    showStats: boolean;
    setShowStats: (show: boolean) => void;
    statsLoading: boolean;
    sessionStats: AccountStatRow[];
    selectedStatsSessionId: number | null;
    statsFilter: 'all' | 'success' | 'failed';
    setStatsFilter: (filter: 'all' | 'success' | 'failed') => void;
    statsSearch: string;
    setStatsSearch: (search: string) => void;
    exportStatsCsv: () => void;
    successCount: number;
    failedCount: number;
    filteredSessionStats: AccountStatRow[];
}

export function SessionStats({
    showStats,
    setShowStats,
    statsLoading,
    sessionStats,
    selectedStatsSessionId,
    statsFilter,
    setStatsFilter,
    statsSearch,
    setStatsSearch,
    exportStatsCsv,
    successCount,
    failedCount,
    filteredSessionStats
}: SessionStatsProps) {
    if (!showStats) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
            <div
                className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm transition-opacity"
                onClick={() => setShowStats(false)}
            />

            <Card className="relative w-full max-w-6xl max-h-[90vh] flex flex-col shadow-premium-lg animate-scale-in border-none overflow-hidden">
                <div className="flex items-center justify-between p-6 border-b border-secondary-100 bg-white">
                    <div className="flex items-center gap-3">
                        <div className="bg-primary-100 p-2 rounded-lg">
                            <BarChart3 className="h-5 w-5 text-primary-600" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-secondary-900">Session Statistics</h3>
                            <p className="text-sm text-secondary-500">
                                {selectedStatsSessionId ? `Detailed breakdown for Session #${selectedStatsSessionId}` : 'Session Details'}
                            </p>
                        </div>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => setShowStats(false)}>
                        <X className="h-5 w-5" />
                    </Button>
                </div>

                <div className="flex-1 overflow-hidden bg-secondary-50/50 flex flex-col min-h-0">
                    {statsLoading ? (
                        <div className="flex flex-col items-center justify-center h-full text-secondary-400">
                            <Loader className="h-10 w-10 animate-spin mb-4 text-primary-500" />
                            <span className="font-medium">Loading statistics...</span>
                        </div>
                    ) : (
                        <>
                            {/* Toolbar */}
                            <div className="p-4 border-b border-secondary-100 bg-white flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                                <div className="flex items-center gap-3">
                                    <div className="flex items-center bg-secondary-100 rounded-lg p-1">
                                        <button
                                            onClick={() => setStatsFilter('all')}
                                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${statsFilter === 'all'
                                                ? 'bg-white text-secondary-900 shadow-sm'
                                                : 'text-secondary-600 hover:text-secondary-900'
                                                }`}
                                        >
                                            All ({sessionStats.length})
                                        </button>
                                        <button
                                            onClick={() => setStatsFilter('success')}
                                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${statsFilter === 'success'
                                                ? 'bg-white text-success-700 shadow-sm'
                                                : 'text-secondary-600 hover:text-success-700'
                                                }`}
                                        >
                                            Success ({successCount})
                                        </button>
                                        <button
                                            onClick={() => setStatsFilter('failed')}
                                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${statsFilter === 'failed'
                                                ? 'bg-white text-danger-700 shadow-sm'
                                                : 'text-secondary-600 hover:text-danger-700'
                                                }`}
                                        >
                                            Failed ({failedCount})
                                        </button>
                                    </div>
                                </div>

                                <div className="flex items-center gap-3 w-full lg:w-auto">
                                    <div className="relative flex-1 lg:w-64">
                                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-secondary-400" />
                                        <Input
                                            type="text"
                                            value={statsSearch}
                                            onChange={(e) => setStatsSearch(e.target.value)}
                                            placeholder="Search by account email..."
                                            className="pl-9 h-9 bg-secondary-50 border-secondary-200"
                                        />
                                    </div>
                                    <Button
                                        onClick={exportStatsCsv}
                                        variant="outline"
                                        size="sm"
                                        className="h-9 gap-2"
                                    >
                                        <Download className="h-4 w-4" />
                                        Export CSV
                                    </Button>
                                </div>
                            </div>

                            {/* Table Content */}
                            <div className="flex-1 overflow-y-auto min-h-0 scrollbar-thin scrollbar-thumb-secondary-300 scrollbar-track-transparent">
                                {sessionStats.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full text-secondary-500">
                                        <BarChart3 className="h-12 w-12 mb-4 opacity-20" />
                                        <p>No statistics available for this session.</p>
                                    </div>
                                ) : filteredSessionStats.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full text-secondary-500">
                                        <Search className="h-12 w-12 mb-4 opacity-20" />
                                        <p>No results match your search or filter.</p>
                                    </div>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-left border-collapse">
                                            <thead className="bg-secondary-50 border-b border-secondary-100 sticky top-0 z-10">
                                                <tr>
                                                    <th className="px-6 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Account</th>
                                                    <th className="px-6 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Status</th>
                                                    <th className="px-6 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Order ID</th>
                                                    <th className="px-6 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Delivery</th>
                                                    <th className="px-6 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Items</th>
                                                    <th className="px-6 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Total</th>
                                                    <th className="px-6 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider w-1/4">Message</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-secondary-100 bg-white">
                                                {filteredSessionStats.map((row, idx) => (
                                                    <tr key={idx} className="hover:bg-secondary-50/50 transition-colors">
                                                        <td className="px-6 py-4 text-sm font-medium text-secondary-900 whitespace-nowrap">
                                                            {row.account}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${row.success
                                                                ? 'bg-success-50 text-success-700 border-success-200'
                                                                : 'bg-danger-50 text-danger-700 border-danger-200'
                                                                }`}>
                                                                {row.success ? (
                                                                    <>
                                                                        <CheckCircle className="w-3 h-3 mr-1.5" />
                                                                        Success
                                                                    </>
                                                                ) : (
                                                                    <>
                                                                        <XCircle className="w-3 h-3 mr-1.5" />
                                                                        Failed
                                                                    </>
                                                                )}
                                                            </span>
                                                        </td>
                                                        <td className="px-6 py-4 text-sm text-secondary-600 font-mono whitespace-nowrap">
                                                            {row.order_id || '—'}
                                                        </td>
                                                        <td className="px-6 py-4 text-sm text-secondary-600 whitespace-nowrap">
                                                            {row.expected_delivery || '—'}
                                                        </td>
                                                        <td className="px-6 py-4 text-sm text-secondary-600 whitespace-nowrap">
                                                            {typeof row.basket_items === 'number' ? row.basket_items : '—'}
                                                        </td>
                                                        <td className="px-6 py-4 text-sm font-medium text-secondary-900 whitespace-nowrap">
                                                            {typeof row.cart_total === 'number' ? `₹${row.cart_total}` : '—'}
                                                        </td>
                                                        <td className="px-6 py-4 text-sm text-secondary-600 break-words max-w-xs">
                                                            {row.message || '—'}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>

                <div className="p-4 border-t border-secondary-100 bg-white flex justify-end">
                    <Button variant="outline" onClick={() => setShowStats(false)}>
                        Close Stats
                    </Button>
                </div>
            </Card>
        </div>
    );
}
