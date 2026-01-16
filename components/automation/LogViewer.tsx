import { X, Loader, Terminal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

interface LogEntry {
    created_at: string;
    email: string;
    log_level: string;
    message: string;
    job_id: number;
    job_type: string;
}

interface LogViewerProps {
    showLogs: boolean;
    setShowLogs: (show: boolean) => void;
    logsLoading: boolean;
    jobLogs: LogEntry[];
    selectedJobId: number | null;
}

export function LogViewer({
    showLogs,
    setShowLogs,
    logsLoading,
    jobLogs,
    selectedJobId
}: LogViewerProps) {
    if (!showLogs) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
            <div
                className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm transition-opacity"
                onClick={() => setShowLogs(false)}
            />

            <Card className="relative w-full max-w-4xl max-h-[85vh] flex flex-col shadow-premium-lg animate-scale-in border-none overflow-hidden">
                <div className="flex items-center justify-between p-6 border-b border-secondary-100 bg-white">
                    <div className="flex items-center gap-3">
                        <div className="bg-secondary-100 p-2 rounded-lg">
                            <Terminal className="h-5 w-5 text-secondary-600" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-secondary-900">Session Logs</h3>
                            <p className="text-sm text-secondary-500">
                                {selectedJobId ? `Viewing logs for Session #${selectedJobId}` : 'Session Details'}
                            </p>
                        </div>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => setShowLogs(false)}>
                        <X className="h-5 w-5" />
                    </Button>
                </div>

                <div className="flex-1 bg-secondary-950 p-4 font-mono text-sm overflow-y-auto scrollbar-thin scrollbar-thumb-secondary-700 scrollbar-track-transparent">
                    {logsLoading ? (
                        <div className="flex flex-col items-center justify-center min-h-full text-secondary-400">
                            <Loader className="h-8 w-8 animate-spin mb-4 text-primary-500" />
                            <span>Loading session logs...</span>
                        </div>
                    ) : jobLogs.length === 0 ? (
                        <div className="flex flex-col items-center justify-center min-h-full text-secondary-500">
                            <Terminal className="h-12 w-12 mb-4 opacity-20" />
                            <p>No logs found for this session.</p>
                        </div>
                    ) : (
                        <div className="space-y-1 pr-2">
                            {jobLogs.map((log, index) => {
                                const logLevel = log.log_level?.toUpperCase() || 'INFO';
                                const logColor =
                                    logLevel === 'ERROR' ? 'text-red-400' :
                                        logLevel === 'WARNING' ? 'text-yellow-400' :
                                            logLevel === 'INFO' ? 'text-blue-400' :
                                                'text-secondary-400';

                                return (
                                    <div key={index} className="flex gap-3 hover:bg-white/5 p-1 rounded transition-colors">
                                        <span className="text-secondary-500 whitespace-nowrap text-xs mt-0.5">
                                            {new Date(log.created_at).toLocaleTimeString()}
                                        </span>
                                        <div className="flex-1 break-words">
                                            <span className="text-secondary-400 mr-2">[{log.email}]</span>
                                            <span className={`font-bold mr-2 text-xs ${logColor}`}>[{logLevel}]</span>
                                            <span className="text-secondary-300">{log.message}</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                <div className="p-4 border-t border-secondary-100 bg-white flex justify-end">
                    <Button variant="outline" onClick={() => setShowLogs(false)}>
                        Close Viewer
                    </Button>
                </div>
            </Card>
        </div>
    );
}
