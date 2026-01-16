import { Trash2, Loader, CheckCircle, SlidersHorizontal, X, RefreshCw, ChevronLeft, ChevronRight, Clock, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface AutomationSession {
    id: number;
    batch_session_id: string;
    automation_type: string;
    status: string;
    batch_size: number;
    total_accounts: number;
    total_batches: number;
    completed_batches: number;
    account_range_start: number;
    account_range_end: number;
    total_jobs: number;
    completed_jobs: number;
    failed_jobs: number;
    started_at: string;
    ended_at?: string;
    config?: any;
    error_message?: string;
}

interface RecentSessionsProps {
    recentSessions: AutomationSession[];
    sessionsLoading: boolean;
    deletingAllSessions: boolean;
    showDeleteSuccess: boolean;
    deleteAllSessions: () => void;
    fetchRecentSessions: () => void;
    stopBatchSession: (id: string) => void;
    fetchSessionLogs: (id: number) => void;
    fetchSessionStats: (id: number) => void;
    sessionSuccessMap: Record<number, { success: number; total: number }>;
    page: number;
    pageSize: number | 'all';
    hasMore: boolean;
    typeFilter: string;
    successFilter: string;
    availableTypes: string[];
    handlePageSizeChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
    handlePrevPage: () => void;
    handleNextPage: () => void;
    handleTypeFilterChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
    handleSuccessFilterChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
    handleClearFilters: () => void;
}

export function RecentSessions({
    recentSessions,
    sessionsLoading,
    deletingAllSessions,
    showDeleteSuccess,
    deleteAllSessions,
    fetchRecentSessions,
    stopBatchSession,
    fetchSessionLogs,
    fetchSessionStats,
    sessionSuccessMap,
    page,
    pageSize,
    hasMore,
    typeFilter,
    successFilter,
    availableTypes,
    handlePageSizeChange,
    handlePrevPage,
    handleNextPage,
    handleTypeFilterChange,
    handleSuccessFilterChange,
    handleClearFilters
}: RecentSessionsProps) {

    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'completed': return 'bg-success-50 text-success-700 border-success-200';
            case 'failed': return 'bg-danger-50 text-danger-700 border-danger-200';
            case 'pending': return 'bg-warning-50 text-warning-700 border-warning-200';
            case 'running': return 'bg-primary-50 text-primary-700 border-primary-200';
            case 'processing': return 'bg-primary-50 text-primary-700 border-primary-200';
            default: return 'bg-secondary-100 text-secondary-700 border-secondary-200';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status.toLowerCase()) {
            case 'completed': return CheckCircle;
            case 'failed': return AlertTriangle;
            case 'pending': return Clock;
            case 'running': return Loader;
            case 'processing': return Loader;
            default: return Clock;
        }
    };

    const getSuccessBadgeColor = (success: number, total: number) => {
        if (total <= 0) return 'text-secondary-600 bg-secondary-100 border-secondary-200';
        if (success >= total) return 'text-success-700 bg-success-50 border-success-200';
        if (success === 0) return 'text-danger-700 bg-danger-50 border-danger-200';
        return 'text-warning-700 bg-warning-50 border-warning-200';
    };

    return (
        <Card className="border-none shadow-premium">
            <CardHeader className="border-b border-secondary-100 bg-secondary-50/30 pb-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <CardTitle className="text-xl text-secondary-900 flex items-center gap-2">
                        <Clock className="h-5 w-5 text-primary-600" />
                        Recent Sessions
                    </CardTitle>
                    <Button
                        onClick={deleteAllSessions}
                        disabled={deletingAllSessions || recentSessions.length === 0}
                        variant="ghost"
                        className="text-danger-600 hover:bg-danger-50 hover:text-danger-700 disabled:opacity-50 h-9 px-3 text-sm"
                    >
                        {deletingAllSessions ? (
                            <>
                                <Loader className="h-4 w-4 animate-spin mr-2" />
                                Deleting...
                            </>
                        ) : showDeleteSuccess ? (
                            <>
                                <CheckCircle className="h-4 w-4 mr-2" />
                                Deleted
                            </>
                        ) : (
                            <>
                                <Trash2 className="h-4 w-4 mr-2" />
                                Delete All History
                            </>
                        )}
                    </Button>
                </div>
            </CardHeader>
            <CardContent className="p-0">
                {/* Toolbar */}
                <div className="p-4 border-b border-secondary-100 bg-white">
                    <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="flex items-center gap-2 text-secondary-600 bg-secondary-50 px-3 py-1.5 rounded-md border border-secondary-200">
                                <SlidersHorizontal className="h-4 w-4" />
                                <span className="text-sm font-medium">Filters</span>
                            </div>

                            <div className="flex items-center gap-2">
                                <select
                                    value={pageSize === 'all' ? 'all' : String(pageSize)}
                                    onChange={handlePageSizeChange}
                                    className="h-9 rounded-md border border-secondary-200 bg-white px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                                >
                                    <option value={20}>20 rows</option>
                                    <option value={200}>200 rows</option>
                                    <option value={500}>500 rows</option>
                                    <option value={'all'}>All rows</option>
                                </select>
                            </div>

                            <div className="flex items-center gap-2">
                                <select
                                    value={typeFilter}
                                    onChange={handleTypeFilterChange}
                                    className="h-9 rounded-md border border-secondary-200 bg-white px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 max-w-[180px]"
                                >
                                    <option value="all">All Types</option>
                                    {Array.from(new Set([
                                        'full_automation',
                                        'login_test',
                                        'add_address',
                                        ...availableTypes
                                    ])).map((t) => (
                                        <option key={t} value={t}>
                                            {t.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="flex items-center gap-2">
                                <select
                                    value={successFilter}
                                    onChange={handleSuccessFilterChange}
                                    className="h-9 rounded-md border border-secondary-200 bg-white px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                                >
                                    <option value="all">All Status</option>
                                    <option value="success">Success</option>
                                    <option value="fail">Failed</option>
                                </select>
                            </div>
                        </div>

                        <div className="flex items-center gap-2 self-end xl:self-auto">
                            {(typeFilter !== 'all' || successFilter !== 'all' || pageSize !== 20) && (
                                <Button
                                    variant="ghost"
                                    onClick={handleClearFilters}
                                    size="sm"
                                    className="h-9 text-secondary-500 hover:text-secondary-900"
                                >
                                    <X className="h-4 w-4 mr-1" />
                                    Clear
                                </Button>
                            )}
                            <Button
                                variant="outline"
                                onClick={() => fetchRecentSessions()}
                                size="sm"
                                className="h-9 gap-2"
                            >
                                <RefreshCw className={`h-3.5 w-3.5 ${sessionsLoading ? 'animate-spin' : ''}`} />
                                Refresh
                            </Button>

                            <div className="h-4 w-px bg-secondary-200 mx-2" />

                            <div className="flex items-center gap-1">
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={handlePrevPage}
                                    disabled={pageSize === 'all' || page === 0 || sessionsLoading}
                                    className="h-9 w-9"
                                >
                                    <ChevronLeft className="h-4 w-4" />
                                </Button>
                                <span className="text-sm text-secondary-600 min-w-[60px] text-center font-medium">
                                    {pageSize === 'all' ? 'All' : `Page ${page + 1}`}
                                </span>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={handleNextPage}
                                    disabled={pageSize === 'all' || !hasMore || sessionsLoading}
                                    className="h-9 w-9"
                                >
                                    <ChevronRight className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Table */}
                {sessionsLoading && recentSessions.length === 0 ? (
                    <div className="flex justify-center items-center h-64">
                        <div className="loading-spinner h-8 w-8 border-4 border-primary-200 border-t-primary-600 rounded-full"></div>
                    </div>
                ) : recentSessions.length === 0 ? (
                    <div className="text-center py-16 bg-secondary-50/30">
                        <Clock className="mx-auto h-12 w-12 text-secondary-300 mb-3" />
                        <h3 className="text-lg font-medium text-secondary-900">No sessions found</h3>
                        <p className="text-secondary-500 text-sm">Start an automation to see history here.</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="border-b border-secondary-100 bg-secondary-50/50 text-xs uppercase tracking-wider text-secondary-500 font-medium">
                                    <th className="px-6 py-4">Session ID</th>
                                    <th className="px-6 py-4">Status</th>
                                    <th className="px-6 py-4">Type</th>
                                    <th className="px-6 py-4">Progress</th>
                                    <th className="px-6 py-4">Success Rate</th>
                                    <th className="px-6 py-4">Range</th>
                                    <th className="px-6 py-4">Started</th>
                                    <th className="px-4 py-4 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-secondary-100 bg-white">
                                {recentSessions.map((session) => {
                                    const StatusIcon = getStatusIcon(session.status);
                                    const progress = `${session.completed_batches}/${session.total_batches} batches (${session.completed_jobs}/${session.total_jobs} jobs)`;
                                    const stats = sessionSuccessMap[session.id];

                                    return (
                                        <tr key={session.id} className="group hover:bg-secondary-50/50 transition-colors">
                                            <td className="px-6 py-4">
                                                <span className="font-mono text-xs font-medium text-secondary-500 bg-secondary-100 px-2 py-1 rounded">
                                                    #{session.id}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${getStatusColor(session.status)}`}>
                                                    <StatusIcon className={`w-3 h-3 mr-1.5 ${session.status === 'running' ? 'animate-spin' : ''}`} />
                                                    {session.status}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-sm font-medium text-secondary-900 capitalize">
                                                {session.automation_type.replace(/_/g, ' ')}
                                            </td>
                                            <td className="px-6 py-4 text-sm text-secondary-600">
                                                {progress}
                                            </td>
                                            <td className="px-6 py-4">
                                                {stats ? (
                                                    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${getSuccessBadgeColor(stats.success, stats.total)}`}>
                                                        {stats.success} / {stats.total}
                                                    </span>
                                                ) : (
                                                    <span className="text-secondary-400 text-sm">—</span>
                                                )}
                                            </td>
                                            <td className="px-6 py-4 text-sm text-secondary-600 font-mono">
                                                {session.account_range_start}-{session.account_range_end}
                                            </td>
                                            <td className="px-6 py-4 text-sm text-secondary-600">
                                                {new Date(session.started_at).toLocaleString()}
                                            </td>
                                            <td className="px-4 py-4 text-right">
                                                <div className="flex items-center justify-end gap-2">
                                                    {(session.status.toLowerCase() === 'running' || session.status.toLowerCase() === 'pending') && (session.completed_batches < session.total_batches) && (
                                                        <Button
                                                            onClick={() => stopBatchSession(session.batch_session_id)}
                                                            variant="destructive"
                                                            size="sm"
                                                            className="h-8 text-xs"
                                                        >
                                                            Stop
                                                        </Button>
                                                    )}
                                                    <Button
                                                        onClick={() => fetchSessionLogs(session.id)}
                                                        variant="secondary"
                                                        size="sm"
                                                        className="h-8 text-xs"
                                                    >
                                                        Logs
                                                    </Button>
                                                    <Button
                                                        onClick={() => fetchSessionStats(session.id)}
                                                        variant="outline"
                                                        size="sm"
                                                        className="h-8 text-xs"
                                                    >
                                                        Stats
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
