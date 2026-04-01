'use client';

import { useState, useEffect, useMemo } from 'react';
import { toast } from 'react-hot-toast';
import { api, automationService, addressesService } from '@/lib/api';
import { AutomationStats } from '@/components/automation/AutomationStats';
import { AutomationConfig } from '@/components/automation/AutomationConfig';
import { ProductManager } from '@/components/automation/ProductManager';
import { RecentSessions } from '@/components/automation/RecentSessions';
import { LogViewer } from '@/components/automation/LogViewer';
import { SessionStats } from '@/components/automation/SessionStats';

// Interfaces
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

interface AutomationStatsData {
  total_accounts: number;
  active_accounts: number;
  total_products: number;
  active_products: number;
}

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

interface Address {
  id: number;
  name: string;
  is_default: boolean;
}

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

export default function AutomationPage() {
  // --- State Management ---

  // Stats
  const [stats, setStats] = useState<AutomationStatsData>({
    total_accounts: 0,
    active_accounts: 0,
    total_products: 0,
    active_products: 0
  });
  const [loading, setLoading] = useState(true);

  // Automation Config
  const [automationRunning, setAutomationRunning] = useState(false);
  const [batchSize, setBatchSize] = useState(1);
  const [accountRangeStart, setAccountRangeStart] = useState(1);
  const [accountRangeEnd, setAccountRangeEnd] = useState(50);
  const [automationType, setAutomationType] = useState('full_automation');
  const [viewMode1, setViewMode1] = useState('mobile');
  const [viewMode, setViewMode] = useState('Desktop');
  const [maxCartValue, setMaxCartValue] = useState<number | ''>('');
  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null);
  const [accountSelectionMode, setAccountSelectionMode] = useState<'range' | 'custom'>('range');
  const [customAccountEmails, setCustomAccountEmails] = useState('');
  const [couponCode, setCouponCode] = useState('');
  const [couponCodesText, setCouponCodesText] = useState('');
  const [gstin, setGstin] = useState('');
  const [businessName, setBusinessName] = useState('');
  const [stealDealProduct, setStealDealProduct] = useState('');
  const [headless, setHeadless] = useState(true);
  const [automationTypeMode, setAutomationTypeMode] = useState<'GROCERY' | 'FLIPKART'>('GROCERY');

  // Data
  const [products, setProducts] = useState<Product[]>([]);
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [newProducts, setNewProducts] = useState<NewProduct[]>([{ product_name: '', product_link: '', quantity: 1 }]);
  const [savingProducts, setSavingProducts] = useState(false);

  // Sessions List
  const [recentSessions, setRecentSessions] = useState<AutomationSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number | 'all'>(20);
  const [hasMore, setHasMore] = useState(false);
  const [typeFilter, setTypeFilter] = useState<'all' | string>('all');
  const [successFilter, setSuccessFilter] = useState<'all' | 'success' | 'fail'>('all');
  const [availableTypes, setAvailableTypes] = useState<string[]>([]);
  const [sessionSuccessMap, setSessionSuccessMap] = useState<Record<number, { success: number; total: number }>>({});
  const [deletingAllSessions, setDeletingAllSessions] = useState(false);
  const [showDeleteSuccess, setShowDeleteSuccess] = useState(false);

  // Modals
  const [showLogs, setShowLogs] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [jobLogs, setJobLogs] = useState<any[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);

  const [showStats, setShowStats] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [sessionStats, setSessionStats] = useState<AccountStatRow[]>([]);
  const [selectedStatsSessionId, setSelectedStatsSessionId] = useState<number | null>(null);
  const [statsFilter, setStatsFilter] = useState<'all' | 'success' | 'failed'>('all');
  const [statsSearch, setStatsSearch] = useState('');

  // --- Effects ---

  useEffect(() => {
    fetchStats();
    fetchRecentSessions(0, 20);
    fetchSessionTypes();
    fetchProducts();
    fetchAddresses();
  }, []);

 // 1. Create a memory for your choice (default to mobile)

const [userPreferredViewMode, setUserPreferredViewMode] = useState('mobile');

// 2. Manage the logic: Force Desktop for specific tasks, otherwise use preference
useEffect(() => {
  const desktopRequiredTypes = [
    'full_automation', 
    'add_address', 
    'add_coupon', 
    'remove_addresses', 
    'clear_cart'
  ];
  
  if (desktopRequiredTypes.includes(automationType)) {
    // If it's a complex task, force Desktop
    setViewMode('desktop',);
  } else {
    // If it's Login Test or other simple tasks, use what you manually clicked
    setViewMode(userPreferredViewMode);
  }
}, [automationType, userPreferredViewMode]);

  // --- Helper Functions ---

  const normalizeFlipkartUrl = (rawUrl: string): string => {
    if (!rawUrl) return rawUrl;
    try {
      const url = new URL(rawUrl);
      const host = url.hostname.toLowerCase();
      if (!host.includes('flipkart.com')) return rawUrl;
      const params = url.searchParams;
      const marketplace = params.get('marketplace');
      if (!marketplace) {
        params.set('marketplace', 'GROCERY');
      }
      url.search = params.toString();
      return url.toString();
    } catch {
      return rawUrl;
    }
  };

  // --- API Calls ---

  const fetchProducts = async () => {
    try {
      const response = await api.get('/products/');
      setProducts(response.data);
    } catch (error) {
      toast.error('Failed to fetch products');
    }
  };

  const fetchAddresses = async () => {
    try {
      const addresses = await addressesService.getAddresses();
      setAddresses(addresses);
      if (!selectedAddressId) {
        const defaultAddress = addresses.find((addr: Address) => addr.is_default);
        if (defaultAddress) {
          setSelectedAddressId(defaultAddress.id);
        }
      }
    } catch (error) {
      console.error('Failed to fetch addresses:', error);
    }
  };

  const fetchStats = async () => {
    try {
      const [accountsCountResponse, productsResponse] = await Promise.all([
        api.get('/users/flipkart/count'),
        api.get('/products/')
      ]);

      const accountsCount = accountsCountResponse.data;
      const products = productsResponse.data;

      setStats({
        total_accounts: accountsCount.total || 0,
        active_accounts: accountsCount.active || 0,
        total_products: products.length,
        active_products: products.filter((p: any) => p.is_active).length
      });
    } catch (error) {
      console.error('Error fetching stats:', error);
      toast.error('Failed to fetch automation statistics');
    } finally {
      setLoading(false);
    }
  };

  const fetchSessionTypes = async () => {
    try {
      const res = await api.get('/automation/session-types');
      const types: string[] = Array.isArray(res.data) ? res.data : [];
      setAvailableTypes(types);
    } catch (e) {
      console.warn('Failed to fetch session types');
    }
  };

  const fetchRecentSessions = async (
    pageArg?: number,
    sizeArg?: number | 'all',
    typeArg?: 'all' | string,
    successArg?: 'all' | 'success' | 'fail'
  ) => {
    setSessionsLoading(true);
    try {
      const p = pageArg ?? page;
      const s = sizeArg ?? pageSize;
      const typeToUse = typeArg ?? typeFilter;
      const successToUse = successArg ?? successFilter;
      const skip = s === 'all' ? 0 : p * (s as number);
      const limit = s === 'all' ? 0 : (s as number);
      const params = new URLSearchParams();
      params.set('skip', String(skip));
      params.set('limit', String(limit));
      if (typeToUse !== 'all') params.set('automation_type', typeToUse);
      if (successToUse !== 'all') params.set('success_filter', successToUse);

      const response = await api.get(`/automation/sessions?${params.toString()}`);
      const sessions: AutomationSession[] = response.data;
      setRecentSessions(sessions);

      if (s !== 'all') {
        setHasMore(sessions.length === (s as number));
      } else {
        setHasMore(false);
      }
      computeSessionsSuccess(sessions);
    } catch (error) {
      console.error('Error fetching recent sessions:', error);
    } finally {
      setSessionsLoading(false);
    }
  };

  const computeSessionsSuccess = async (sessions: AutomationSession[]) => {
    try {
      const entries = await Promise.all(
        sessions.map(async (session) => {
          try {
            const data = await automationService.getSessionJobs(session.id);
            const jobs: any[] = data.jobs || [];
            const successfulAccounts = new Set<string>();

            for (const job of jobs) {
              const logs: any[] = job.logs || [];
              for (let i = logs.length - 1; i >= 0; i--) {
                const msg: string = logs[i]?.message || '';
                if (msg.startsWith('Job completed successfully')) {
                  const idx = msg.indexOf('Result: ');
                  if (idx !== -1) {
                    const jsonStr = msg.substring(idx + 'Result: '.length).trim();
                    try {
                      const result = JSON.parse(jsonStr);
                      if (result && result.success === true) {
                        const acc = typeof result.account === 'string' ? result.account : undefined;
                        if (acc) successfulAccounts.add(acc);
                        else successfulAccounts.add(`job-${job.id}`);
                      }
                    } catch (e) { /* ignore */ }
                  }
                  break;
                }
              }
            }

            const success = successfulAccounts.size;
            const total = typeof session.total_accounts === 'number' ? session.total_accounts : (jobs?.length || 0);
            return [session.id, { success, total }] as const;
          } catch (e) {
            return [session.id, { success: 0, total: session.total_accounts || 0 }] as const;
          }
        })
      );

      const map: Record<number, { success: number; total: number }> = {};
      for (const [sid, val] of entries) map[sid] = val;
      setSessionSuccessMap(map);
    } catch (e) { /* ignore */ }
  };

  // --- Actions ---

  const startAutomation = async () => {
    // Validation
    if (accountSelectionMode === 'range') {
      if (accountRangeStart > accountRangeEnd) {
        toast.error('Invalid account range.');
        return;
      }
    } else {
      const emails = customAccountEmails.split(',').map(e => e.trim()).filter(e => e !== '');
      if (emails.length === 0) {
        toast.error('Please enter at least one email address');
        return;
      }
    }

    if (batchSize < 1 || batchSize > 5) {
      toast.error('Batch size must be between 1 and 5');
      return;
    }

    setAutomationRunning(true);

    try {
      const requestData: any = {
        batch_size: batchSize,
        automation_type: automationType,
        view_mode: viewMode,
        max_cart_value: maxCartValue || null,
        address_id: selectedAddressId,
        account_selection_mode: accountSelectionMode,
        headless: headless,
        automation_mode: automationTypeMode
      };

      if (accountSelectionMode === 'range') {
        requestData.account_range_start = accountRangeStart;
        requestData.account_range_end = accountRangeEnd;
      } else {
        requestData.custom_account_emails = customAccountEmails.split(',').map(e => e.trim()).filter(e => e !== '');
      }

      if (automationType === 'add_coupon') {
        if (accountSelectionMode === 'custom') {
          const codes = couponCodesText.split(/\n|,/).map(c => c.trim()).filter(c => c !== '');
          requestData.coupon_codes = codes;
        } else {
          requestData.coupon_code = couponCode.trim();
        }
      }

      if (automationType === 'full_automation') {
        if (gstin && gstin.trim() !== '') requestData.gstin = gstin.trim();
        if (businessName && businessName.trim() !== '') requestData.business_name = businessName.trim();
        if (stealDealProduct && stealDealProduct.trim() !== '') requestData.steal_deal_product = stealDealProduct.trim();
      }

      const response = await api.post('/automation/start-automation', requestData);
      toast.success(response.data.message);

      setTimeout(() => {
        fetchRecentSessions();
      }, 2000);

    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to start automation');
    } finally {
      setAutomationRunning(false);
    }
  };

  const startLoginTest = async () => {
    setAutomationType('login_test');
    // Reuse startAutomation logic but force login_test params if needed, 
    // but the original code had separate logic. Let's adapt it.

    if (accountSelectionMode === 'range' && accountRangeStart > accountRangeEnd) {
      toast.error('Invalid account range.');
      return;
    }

    setAutomationRunning(true);
    try {
      const requestData: any = {
        batch_size: batchSize,
        automation_type: 'login_test',
        view_mode: viewMode,
        address_id: selectedAddressId,
        account_selection_mode: accountSelectionMode,
        keep_browser_open: true,
        headless: headless,
        automation_mode: automationTypeMode
      };

      if (accountSelectionMode === 'range') {
        requestData.account_range_start = accountRangeStart;
        requestData.account_range_end = accountRangeEnd;
      } else {
        requestData.custom_account_emails = customAccountEmails.split(',').map(e => e.trim()).filter(e => e !== '');
      }

      const response = await api.post('/automation/start-automation', requestData);
      toast.success(response.data.message);
      toast.success('Browsers will remain open. Close them manually.');

      setTimeout(() => {
        fetchRecentSessions();
      }, 2000);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to start login test');
    } finally {
      setAutomationRunning(false);
    }
  };

  const stopBatchSession = async (batchSessionId: string) => {
    if (!confirm('Stop remaining pending batches?')) return;
    try {
      await api.post(`/automation/stop-batch/${batchSessionId}`);
      toast.success('Stop requested.');
      setTimeout(() => fetchRecentSessions(), 1000);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Failed to stop session');
    }
  };

  const deleteAllSessions = async () => {
    if (!confirm('Delete ALL automation sessions and logs? This cannot be undone.')) return;
    setDeletingAllSessions(true);
    try {
      const response = await api.delete('/automation/sessions/all');
      toast.success(`Deleted ${response.data.deleted.sessions} sessions`);
      setShowDeleteSuccess(true);
      setTimeout(() => setShowDeleteSuccess(false), 3000);
      fetchRecentSessions();
    } catch (e: any) {
      toast.error('Failed to delete sessions');
    } finally {
      setDeletingAllSessions(false);
    }
  };

  // --- Product Handlers ---

  const handleAddProduct = () => {
    setNewProducts([...newProducts, { product_name: '', product_link: '', quantity: 1 }]);
  };

  const handleProductChange = (index: number, field: keyof NewProduct, value: string | number) => {
    const updatedProducts = [...newProducts];
    (updatedProducts[index] as any)[field] = value;
    setNewProducts(updatedProducts);
  };

  const handleRemoveProduct = (index: number) => {
    const updatedProducts = newProducts.filter((_, i) => i !== index);
    setNewProducts(updatedProducts);
  };

  const handleSaveProducts = async () => {
    const validProducts = newProducts.filter(p => p.product_link.trim() !== '' && p.quantity > 0);
    if (validProducts.length === 0) {
      toast.error('Please add at least one valid product.');
      return;
    }

    setSavingProducts(true);
    try {
      const normalizedProducts = validProducts.map(p => ({
        ...p,
        product_link: normalizeFlipkartUrl(p.product_link),
      }));
      const response = await api.post('/products/bulk', normalizedProducts);
      toast.success(`${response.data.length} products saved!`);
      setNewProducts([{ product_name: '', product_link: '', quantity: 1 }]);
      fetchProducts();
      fetchStats();
    } catch (error: any) {
      toast.error('Failed to save products.');
    } finally {
      setSavingProducts(false);
    }
  };

  const handleDeleteProduct = async (id: number) => {
    if (!confirm('Delete this product?')) return;
    try {
      await api.delete(`/products/${id}`);
      toast.success('Product deleted.');
      fetchProducts();
      fetchStats();
    } catch (error) {
      toast.error('Failed to delete product.');
    }
  };

  // --- Log & Stats Viewers ---

  const fetchSessionLogs = async (sessionId: number) => {
    setLogsLoading(true);
    try {
      const data = await automationService.getSessionJobs(sessionId);
      const allLogs: any[] = [];
      data.jobs.forEach((job: any) => {
        let jobData = job.job_data;
        if (typeof jobData === 'string') {
          try { jobData = JSON.parse(jobData); } catch (e) { jobData = {}; }
        }
        job.logs.forEach((log: any) => {
          allLogs.push({
            ...log,
            job_id: job.id,
            job_type: job.job_type,
            email: jobData?.email || 'Unknown'
          });
        });
      });
      allLogs.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
      setJobLogs(allLogs);
      setSelectedJobId(sessionId);
      setShowLogs(true);
    } catch (error) {
      toast.error('Failed to load logs');
    } finally {
      setLogsLoading(false);
    }
  };

  const fetchSessionStats = async (sessionId: number) => {
    setStatsLoading(true);
    try {
      const data = await automationService.getSessionJobs(sessionId);
      const rows: AccountStatRow[] = [];

      for (const job of data.jobs || []) {
        let jobData = job.job_data;
        if (typeof jobData === 'string') {
          try { jobData = JSON.parse(jobData); } catch { jobData = {}; }
        }
        const email: string = jobData?.email || 'Unknown';

        let result: any = null;
        const logs: any[] = job.logs || [];
        for (let i = logs.length - 1; i >= 0; i--) {
          const msg: string = logs[i]?.message || '';
          if (msg.startsWith('Job completed successfully')) {
            const idx = msg.indexOf('Result: ');
            if (idx !== -1) {
              const jsonStr = msg.substring(idx + 'Result: '.length).trim();
              try { result = JSON.parse(jsonStr); } catch { /* ignore */ }
            }
            break;
          }
        }

        const messageFromResult = result?.message;
        const derivedMessage = messageFromResult ||
          (result?.cancel_reason ? `Reason: ${result.cancel_reason}` : undefined) ||
          (result?.error ? `Error: ${result.error}` : undefined) ||
          job.error_message;

        const row: AccountStatRow = {
          account: (result?.account as string) || email,
          order_id: result?.order_id,
          expected_delivery: result?.expected_delivery,
          basket_items: result?.basket_items,
          cart_total: result?.cart_total,
          address: result?.delivery_address_name,
          success: result?.success === true,
          message: derivedMessage,
        };

        if (!result && job.status && job.status.toLowerCase() === 'failed') {
          row.success = false;
          row.message = job.error_message || 'Job failed';
        }

        rows.push(row);
      }

      setSessionStats(rows);
      setSelectedStatsSessionId(sessionId);
      setShowStats(true);
    } catch (e) {
      toast.error('Failed to load stats');
    } finally {
      setStatsLoading(false);
    }
  };

  const filteredSessionStats = useMemo(() => {
    const term = statsSearch.trim().toLowerCase();
    return sessionStats.filter(row => {
      const passesFilter =
        statsFilter === 'all' ||
        (statsFilter === 'success' && row.success) ||
        (statsFilter === 'failed' && !row.success);
      const passesSearch = term === '' || (row.account || '').toLowerCase().includes(term);
      return passesFilter && passesSearch;
    });
  }, [sessionStats, statsFilter, statsSearch]);

  const exportStatsCsv = () => {
    const header = ['account', 'order_id', 'expected_delivery', 'basket_items', 'cart_total', 'address', 'success', 'message'];
    const lines = [header.join(',')];
    const esc = (v: any) => {
      if (v === null || v === undefined) return '';
      const s = String(v);
      if (s.includes(',') || s.includes('\n') || s.includes('"')) {
        return '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    };
    for (const r of filteredSessionStats) {
      lines.push([
        esc(r.account),
        esc(r.order_id),
        esc(r.expected_delivery),
        esc(r.basket_items),
        esc(r.cart_total),
        esc(r.address),
        esc(r.success ? 'true' : 'false'),
        esc(r.message)
      ].join(','));
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `session_${selectedStatsSessionId || 'stats'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const successCount = useMemo(() => sessionStats.filter(r => r.success).length, [sessionStats]);
  const failedCount = useMemo(() => sessionStats.filter(r => !r.success).length, [sessionStats]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="loading-spinner h-12 w-12 border-4 border-primary-200 border-t-primary-600 rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in pb-8">
      <AutomationStats
        stats={stats}
        batchSize={batchSize}
        accountSelectionMode={accountSelectionMode}
        accountRangeStart={accountRangeStart}
        accountRangeEnd={accountRangeEnd}
        customAccountEmails={customAccountEmails}
      />

      <AutomationConfig
        batchSize={batchSize} setBatchSize={setBatchSize}
        accountSelectionMode={accountSelectionMode} setAccountSelectionMode={setAccountSelectionMode}
        headless={headless} setHeadless={setHeadless}
        accountRangeStart={accountRangeStart} setAccountRangeStart={setAccountRangeStart}
        accountRangeEnd={accountRangeEnd} setAccountRangeEnd={setAccountRangeEnd}
        customAccountEmails={customAccountEmails} setCustomAccountEmails={setCustomAccountEmails}
        automationType={automationType} setAutomationType={setAutomationType}
        automationTypeMode={automationTypeMode} setAutomationTypeMode={setAutomationTypeMode}
        selectedAddressId={selectedAddressId} setSelectedAddressId={setSelectedAddressId}
        addresses={addresses}
        maxCartValue={maxCartValue} setMaxCartValue={setMaxCartValue}
        viewMode={viewMode} 
        setViewMode={(val) => {
        setViewMode(val);           
        setUserPreferredViewMode(val); 
        }}
        couponCode={couponCode} setCouponCode={setCouponCode}
        couponCodesText={couponCodesText} setCouponCodesText={setCouponCodesText}
        gstin={gstin} setGstin={setGstin}
        businessName={businessName} setBusinessName={setBusinessName}
        stealDealProduct={stealDealProduct} setStealDealProduct={setStealDealProduct}
        automationRunning={automationRunning}
        startAutomation={startAutomation}
        startLoginTest={startLoginTest}
        activeAccountsCount={stats.active_accounts}
      />

      <ProductManager
        products={products}
        newProducts={newProducts}
        setNewProducts={setNewProducts}
        savingProducts={savingProducts}
        handleAddProduct={handleAddProduct}
        handleProductChange={handleProductChange}
        handleRemoveProduct={handleRemoveProduct}
        handleSaveProducts={handleSaveProducts}
        handleDeleteProduct={handleDeleteProduct}
      />

      <RecentSessions
        recentSessions={recentSessions}
        sessionsLoading={sessionsLoading}
        deletingAllSessions={deletingAllSessions}
        showDeleteSuccess={showDeleteSuccess}
        deleteAllSessions={deleteAllSessions}
        fetchRecentSessions={fetchRecentSessions}
        stopBatchSession={stopBatchSession}
        fetchSessionLogs={fetchSessionLogs}
        fetchSessionStats={fetchSessionStats}
        sessionSuccessMap={sessionSuccessMap}
        page={page}
        pageSize={pageSize}
        hasMore={hasMore}
        typeFilter={typeFilter}
        successFilter={successFilter}
        availableTypes={availableTypes}
        handlePageSizeChange={(e) => {
          const val = e.target.value === 'all' ? 'all' : Number(e.target.value);
          setPageSize(val);
          setPage(0);
          fetchRecentSessions(0, val, typeFilter, successFilter);
        }}
        handlePrevPage={() => {
          if (page > 0 && pageSize !== 'all') {
            const newPage = page - 1;
            setPage(newPage);
            fetchRecentSessions(newPage, pageSize);
          }
        }}
        handleNextPage={() => {
          if (pageSize !== 'all' && hasMore) {
            const newPage = page + 1;
            setPage(newPage);
            fetchRecentSessions(newPage, pageSize);
          }
        }}
        handleTypeFilterChange={(e) => {
          const val = e.target.value;
          setTypeFilter(val);
          setPage(0);
          fetchRecentSessions(0, pageSize, val, successFilter);
        }}
        handleSuccessFilterChange={(e) => {
          const val = e.target.value as 'all' | 'success' | 'fail';
          setSuccessFilter(val);
          setPage(0);
          fetchRecentSessions(0, pageSize, typeFilter, val);
        }}
        handleClearFilters={() => {
          setTypeFilter('all');
          setSuccessFilter('all');
          setPageSize(20);
          setPage(0);
          fetchRecentSessions(0, 20, 'all', 'all');
        }}
      />

      <LogViewer
        showLogs={showLogs}
        setShowLogs={setShowLogs}
        logsLoading={logsLoading}
        jobLogs={jobLogs}
        selectedJobId={selectedJobId}
      />

      <SessionStats
        showStats={showStats}
        setShowStats={setShowStats}
        statsLoading={statsLoading}
        sessionStats={sessionStats}
        selectedStatsSessionId={selectedStatsSessionId}
        statsFilter={statsFilter}
        setStatsFilter={setStatsFilter}
        statsSearch={statsSearch}
        setStatsSearch={setStatsSearch}
        exportStatsCsv={exportStatsCsv}
        successCount={successCount}
        failedCount={failedCount}
        filteredSessionStats={filteredSessionStats}
      />
    </div>
  );
}

