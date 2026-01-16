'use client';

import { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import { api, automationService } from '@/lib/api';
import { Users, Plus, Upload, Download, Trash2, Edit, Mail, CheckCircle, XCircle, Loader } from 'lucide-react';

interface FlipkartAccount {
  id: number;
  email: string;
  cookies?: string | null;
  is_active: boolean;
  last_login: string | null;
  login_attempts: number;
  created_at: string;
}

interface AccountResultRow {
  session_id: number;
  job_id: number;
  account: string;
  order_id?: string;
  expected_delivery?: string;
  basket_items?: number;
  cart_total?: number;
  address?: string;
  success?: boolean;
  message?: string;
  created_at?: string;
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<FlipkartAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingAccount, setEditingAccount] = useState<FlipkartAccount | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [selectedAccountEmail, setSelectedAccountEmail] = useState<string | null>(null);
  // Account Results Modal state
  const [showResults, setShowResults] = useState(false);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [accountResults, setAccountResults] = useState<AccountResultRow[]>([]);
  // Pagination state
  const [pageSize, setPageSize] = useState<number | 'all'>(100);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalAccounts, setTotalAccounts] = useState(0);

  // Form state
  const [formData, setFormData] = useState({
    email: ''
  });

  useEffect(() => {
    fetchAccounts();
  }, [pageSize, currentPage]);

  const fetchAccounts = async () => {
    try {
      const limit = pageSize === 'all' ? 10000 : pageSize;
      const skip = pageSize === 'all' ? 0 : (currentPage - 1) * pageSize;
      const response = await api.get(`/users/flipkart?limit=${limit}&skip=${skip}`);
      setAccounts(response.data);

      // Get total count for pagination
      if (pageSize !== 'all') {
        const countResponse = await api.get('/users/flipkart/count');
        setTotalAccounts(countResponse.data.total);
      } else {
        setTotalAccounts(response.data.length);
      }
    } catch (error) {
      toast.error('Failed to fetch Flipkart accounts');
      console.error('Error fetching accounts:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePageSizeChange = (newPageSize: number | 'all') => {
    setPageSize(newPageSize);
    setCurrentPage(1);
  };

  const totalPages = pageSize === 'all' ? 1 : Math.ceil(totalAccounts / pageSize);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      if (editingAccount) {
        // Update existing account
        const response = await api.put(`/users/flipkart/${editingAccount.id}`, formData);
        setAccounts(accounts.map(a => a.id === editingAccount.id ? response.data : a));
        toast.success('Account updated successfully');
        setEditingAccount(null);
      } else {
        // Create new account
        const response = await api.post('/users/flipkart', formData);
        setAccounts([response.data, ...accounts]);
        toast.success('Account added successfully');
        setShowAddForm(false);
      }

      // Reset form
      setFormData({
        email: ''
      });
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to save account');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this Flipkart account?')) return;

    try {
      await api.delete(`/users/flipkart/${id}`);
      setAccounts(accounts.filter(a => a.id !== id));
      toast.success('Account deleted successfully');
    } catch (error) {
      toast.error('Failed to delete account');
    }
  };

  const handleEdit = (account: FlipkartAccount) => {
    setEditingAccount(account);
    setFormData({
      email: account.email
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
      const response = await api.post('/users/flipkart/import-csv', formData, {
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
      fetchAccounts(); // Refresh the list
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to import CSV');
    } finally {
      setImporting(false);
    }
  };

  const downloadTemplate = async () => {
    try {
      const response = await api.get('/users/flipkart/export-template', {
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'flipkart_accounts_template.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      toast.success('Template downloaded successfully');
    } catch (error) {
      toast.error('Failed to download template');
    }
  };

  const toggleAccountStatus = async (account: FlipkartAccount) => {
    try {
      const response = await api.put(`/users/flipkart/${account.id}`, {
        is_active: !account.is_active
      });
      setAccounts(accounts.map(a => a.id === account.id ? response.data : a));
      toast.success(`Account ${response.data.is_active ? 'activated' : 'deactivated'}`);
    } catch (error) {
      toast.error('Failed to update account status');
    }
  };

  const testLogin = async (accountId: number) => {
    try {
      const response = await api.post(`/users/flipkart/${accountId}/test-login`);
      if (response.data.success) {
        toast.success('Login test successful');
      } else {
        toast.error('Login test failed');
      }
    } catch (error) {
      toast.error('Failed to test login');
    }
  };

  // Fetch and show parsed automation results for a specific account email across recent sessions
  const openAccountResults = async (email: string) => {
    setSelectedAccountEmail(email);
    setShowResults(true);
    setResultsLoading(true);
    try {
      const sessions = await automationService.getSessions({ limit: 25 });
      const rows: AccountResultRow[] = [];

      for (const session of sessions || []) {
        try {
          const data = await automationService.getSessionJobs(session.id);
          for (const job of (data.jobs || [])) {
            // Parse job_data
            let jobData = job.job_data;
            if (typeof jobData === 'string') {
              try { jobData = JSON.parse(jobData); } catch { jobData = {}; }
            }
            const jobEmail = jobData?.email || 'Unknown';
            if (!jobEmail || jobEmail.toLowerCase() !== email.toLowerCase()) continue;

            // Find completion result log
            let result: any = null;
            let resultCreatedAt: string | undefined = undefined;
            const logs: any[] = job.logs || [];
            for (let i = logs.length - 1; i >= 0; i--) {
              const msg: string = logs[i]?.message || '';
              if (msg.startsWith('Job completed successfully')) {
                const idx = msg.indexOf('Result: ');
                if (idx !== -1) {
                  const jsonStr = msg.substring(idx + 'Result: '.length).trim();
                  try {
                    result = JSON.parse(jsonStr);
                    resultCreatedAt = logs[i]?.created_at;
                  } catch { /* ignore */ }
                }
                break;
              }
            }

            const messageFromResult = result?.message as string | undefined;
            const cancelReason = result?.cancel_reason as string | undefined;
            const errorReason = result?.error as string | undefined;
            const derivedMessage = messageFromResult ||
              (cancelReason ? `Reason: ${cancelReason}` : undefined) ||
              (errorReason ? `Error: ${errorReason}` : undefined) ||
              job.error_message || undefined;

            const row: AccountResultRow = {
              session_id: session.id,
              job_id: job.id,
              account: (result?.account as string) || jobEmail,
              order_id: result?.order_id,
              expected_delivery: result?.expected_delivery,
              basket_items: typeof result?.basket_items === 'number' ? result.basket_items : undefined,
              cart_total: typeof result?.cart_total === 'number' ? result.cart_total : undefined,
              address: result?.delivery_address_name,
              success: result?.success === true,
              message: derivedMessage,
              created_at: resultCreatedAt || job.completed_at || job.started_at || job.created_at,
            };

            if (!result && job.status && String(job.status).toLowerCase() === 'failed') {
              row.success = false;
              row.message = job.error_message || 'Job failed';
            }

            rows.push(row);
          }
        } catch (e) {
          // ignore session errors
        }
      }

      // Sort newest first
      rows.sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());
      setAccountResults(rows);
    } catch (e) {
      toast.error('Failed to load automation results');
    } finally {
      setResultsLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="loading-spinner h-12 w-12 border-4 border-primary-200 border-t-primary-600 rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center">
            <Users className="mr-3 h-8 w-8 text-blue-600" />
            Flipkart Accounts
          </h1>
          <p className="text-gray-600 mt-2">
            Manage Flipkart accounts for automated login and ordering
          </p>
        </div>

        <div className="flex space-x-3">
          <button
            onClick={downloadTemplate}
            className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 flex items-center"
          >
            <Download className="mr-2 h-4 w-4" />
            Download Template
          </button>
          <button
            onClick={() => setShowAddForm(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center"
          >
            <Plus className="mr-2 h-4 w-4" />
            Add Account
          </button>
        </div>
      </div>

      {/* CSV Import Section */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
          <Upload className="mr-2 h-5 w-5" />
          Import Accounts from CSV
        </h3>
        <div className="flex items-center space-x-4">
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
            className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-gray-900 bg-white"
          />
          <button
            onClick={handleCsvImport}
            disabled={!csvFile || importing}
            className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:bg-gray-400 flex items-center"
          >
            {importing ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Importing...
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Import CSV
              </>
            )}
          </button>
        </div>
        <p className="text-sm text-gray-500 mt-2">
          Upload a CSV file with column: email (required)
        </p>
      </div>

      {/* Gmail Configuration Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex">
          <Mail className="h-5 w-5 text-blue-600 mt-0.5 mr-2" />
          <div>
            <h4 className="text-sm font-medium text-blue-800">OTP Configuration</h4>
            <p className="text-sm text-blue-600 mt-1">
              OTPs will be automatically fetched from: <strong>vkkykh@kanuvk.com</strong>
              <br />
              All Flipkart accounts will use OTP-based login. No passwords needed.
            </p>
          </div>
        </div>
      </div>

      {/* Add/Edit Account Form */}
      {showAddForm && (
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            {editingAccount ? 'Edit Flipkart Account' : 'Add New Flipkart Account'}
          </h3>

          <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Flipkart Email *
              </label>
              <input
                type="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="your-flipkart-account@example.com"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                The email address used to login to Flipkart. OTPs will be automatically fetched from vkkykh@kanuvk.com.
              </p>
            </div>

            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={() => {
                  setShowAddForm(false);
                  setEditingAccount(null);
                  setFormData({
                    email: ''
                  });
                }}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                {editingAccount ? 'Update Account' : 'Add Account'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Accounts List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Accounts ({pageSize === 'all' ? totalAccounts : accounts.length} of {totalAccounts})</h3>
              <p className="text-sm text-gray-600 mt-1">
                Numbers shown for active accounts correspond to the automation range selection (ordered by account ID)
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-700">Show:</span>
                <select
                  value={pageSize}
                  onChange={(e) => handlePageSizeChange(e.target.value === 'all' ? 'all' : parseInt(e.target.value))}
                  className="border border-gray-300 rounded-md px-3 py-1 text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value={100}>100</option>
                  <option value={500}>500</option>
                  <option value="all">All</option>
                </select>
              </div>
              {pageSize !== 'all' && totalPages > 1 && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                    disabled={currentPage === 1}
                    className="px-3 py-1 text-sm text-gray-700 bg-white border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-gray-700">
                    Page {currentPage} of {totalPages}
                  </span>
                  <button
                    onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                    disabled={currentPage === totalPages}
                    className="px-3 py-1 text-sm text-gray-700 bg-white border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                  >
                    Next
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {accounts.length === 0 ? (
          <div className="text-center py-12">
            <Users className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No accounts</h3>
            <p className="mt-1 text-sm text-gray-500">Get started by adding a new Flipkart account or importing from CSV.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    #
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Account
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Cookies
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Last Login
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Automation Results
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {accounts
                  .sort((a, b) => a.id - b.id)
                  .map((account, index) => {
                    // Calculate continuous account number across pages
                    const pageOffset = pageSize === 'all' ? 0 : (currentPage - 1) * pageSize;
                    const accountNumber = account.is_active ? pageOffset + index + 1 : null;

                    return (
                      <tr key={account.id}>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span className={`text-sm font-medium ${account.is_active ? 'text-blue-600' : 'text-gray-400'}`}>
                            {accountNumber || '-'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <Mail className="h-4 w-4 text-gray-400 mr-2" />
                            <div>
                              <div className="text-sm font-medium text-gray-900">
                                {account.email}
                              </div>
                              <div className="text-sm text-gray-500">
                                Login attempts: {account.login_attempts}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <button
                            onClick={() => toggleAccountStatus(account)}
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${account.is_active
                              ? 'bg-green-100 text-green-800'
                              : 'bg-red-100 text-red-800'
                              }`}
                          >
                            {account.is_active ? (
                              <>
                                <CheckCircle className="w-3 h-3 mr-1" />
                                Active
                              </>
                            ) : (
                              <>
                                <XCircle className="w-3 h-3 mr-1" />
                                Inactive
                              </>
                            )}
                          </button>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${account.cookies ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                            }`}>
                            {account.cookies ? (
                              <>
                                <CheckCircle className="w-3 h-3 mr-1" />
                                Saved
                              </>
                            ) : (
                              <>
                                <XCircle className="w-3 h-3 mr-1" />
                                None
                              </>
                            )}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {account.last_login
                            ? new Date(account.last_login).toLocaleDateString()
                            : 'Never'
                          }
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <button
                            onClick={() => openAccountResults(account.email)}
                            className="text-green-700 hover:text-green-900 bg-green-50 px-3 py-1 rounded-md text-xs font-medium"
                          >
                            Results
                          </button>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <div className="flex space-x-2">
                            <button
                              onClick={() => testLogin(account.id)}
                              className="text-green-600 hover:text-green-900 text-xs bg-green-50 px-2 py-1 rounded"
                            >
                              Test Login
                            </button>
                            <button
                              onClick={() => handleEdit(account)}
                              className="text-blue-600 hover:text-blue-900"
                            >
                              <Edit className="h-4 w-4" />
                            </button>
                            <button
                              onClick={() => handleDelete(account.id)}
                              className="text-red-600 hover:text-red-900"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {/* Account Automation Results Modal */}
      {showResults && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-11/12 max-w-6xl shadow-lg rounded-md bg-white">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-900">
                Automation Results {selectedAccountEmail && `(${selectedAccountEmail})`}
              </h3>
              <button onClick={() => setShowResults(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>

            {resultsLoading ? (
              <div className="flex justify-center items-center py-8">
                <Loader className="animate-spin h-8 w-8 text-blue-500" />
                <span className="ml-2 text-gray-600">Loading results...</span>
              </div>
            ) : (
              <div className="max-h-[70vh] overflow-y-auto bg-gray-50 rounded-lg p-4">
                {accountResults.length === 0 ? (
                  <p className="text-gray-500 text-center py-4">No automation results found for this account.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-100 sticky top-0 z-10">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">When</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Session</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Order ID</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Expected Delivery</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Basket Items</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Cart Total</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Address</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Success</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Message</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {accountResults.map((row, idx) => (
                          <tr key={`${row.session_id}-${row.job_id}-${idx}`} className={row.success ? 'bg-green-50' : 'bg-red-50'}>
                            <td className="px-4 py-2 text-sm text-gray-700 whitespace-nowrap">{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</td>
                            <td className="px-4 py-2 text-sm text-blue-700 whitespace-nowrap">#{row.session_id}</td>
                            <td className="px-4 py-2 text-sm text-gray-700 whitespace-nowrap">{row.order_id || '—'}</td>
                            <td className="px-4 py-2 text-sm text-gray-700 whitespace-nowrap">{row.expected_delivery || '—'}</td>
                            <td className="px-4 py-2 text-sm text-gray-700 whitespace-nowrap">{typeof row.basket_items === 'number' ? row.basket_items : '—'}</td>
                            <td className="px-4 py-2 text-sm text-gray-700 whitespace-nowrap">{typeof row.cart_total === 'number' ? row.cart_total : '—'}</td>
                            <td className="px-4 py-2 text-sm text-gray-700 whitespace-nowrap">{row.address || '—'}</td>
                            <td className="px-4 py-2 text-sm font-semibold whitespace-nowrap">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${row.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                                {row.success ? 'true' : 'false'}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-700 whitespace-pre-wrap">{row.message || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-end mt-4">
              <button
                onClick={() => setShowResults(false)}
                className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
