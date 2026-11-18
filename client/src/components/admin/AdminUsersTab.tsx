import React, { useEffect, useState } from 'react';
import { Flame, RefreshCw, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export interface AdminUserRecord {
  id: number;
  username: string;
  email: string;
  created_at?: string | null;
  is_admin: boolean;
  total_points: number;
  total_wins: number;
  games_played: number;
  current_streak: number;
}

interface AdminUsersTabProps {
  users: AdminUserRecord[];
  totalUsers: number;
  search: string;
  page: number;
  isLoading: boolean;
  error: string | null;
  onSearchChange: (search: string) => void;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
}

const PAGE_SIZE = 25;

export const AdminUsersTab: React.FC<AdminUsersTabProps> = ({
  users,
  totalUsers,
  search,
  page,
  isLoading,
  error,
  onSearchChange,
  onPageChange,
  onRefresh,
}) => {
  const { t } = useTranslation();
  const [inputSearch, setInputSearch] = useState(search);
  const locale = 'en-US';
  const numberFormat = new Intl.NumberFormat(locale);
  const dateFormat = new Intl.DateTimeFormat(locale, { dateStyle: 'medium' });
  const pageCount = Math.ceil(totalUsers / PAGE_SIZE);

  useEffect(() => setInputSearch(search), [search]);
  useEffect(() => {
    if (inputSearch === search) return;
    const timer = window.setTimeout(() => onSearchChange(inputSearch), 300);
    return () => window.clearTimeout(timer);
  }, [inputSearch, onSearchChange, search]);
  const queryPending = inputSearch !== search;
  const loading = isLoading || queryPending;

  return (
    <section className="min-w-0 space-y-4 bg-app-canvas text-app-text" aria-labelledby="admin-page-title">
      <div className="flex flex-wrap items-end justify-between gap-3 rounded-md border border-app-border bg-app-surface p-4">
        <div className="min-w-0 flex-1 sm:max-w-xl">
          <label htmlFor="admin-users-search" className="mb-1 block text-sm font-medium text-app-text-secondary">{t('adminUsers.searchLabel')}</label>
          <div className="relative">
            <Search aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 text-app-text-muted" size={16} />
            <input
              id="admin-users-search"
              type="search"
              value={inputSearch}
              onChange={(event) => setInputSearch(event.target.value)}
              placeholder={t('adminUsers.searchPlaceholder')}
              className="min-h-11 w-full max-w-full rounded-md border border-app-border bg-app-surface-muted py-2 pl-10 pr-3 text-sm text-app-text placeholder:text-app-text-muted focus:border-app-accent focus:outline-none focus:ring-2 focus:ring-app-focus"
            />
          </div>
        </div>
        <button type="button" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-app-border bg-app-surface-muted px-3 py-2 text-sm font-medium text-app-text transition-colors hover:bg-app-surface-raised focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50" onClick={onRefresh} disabled={loading}>
          <RefreshCw aria-hidden="true" size={15} />
          {loading ? t('adminCommon.updating') : t('adminCommon.refresh')}
        </button>
      </div>
      {error && !queryPending && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-rose-300 bg-rose-50 p-4 text-rose-800">
          <span>{t(error)}</span>
          <button type="button" className="min-h-11 rounded-md border border-rose-300 bg-white px-3 py-2 text-sm font-medium text-rose-800 transition-colors hover:bg-rose-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50" onClick={onRefresh} disabled={loading}>{t('adminCommon.retry')}</button>
        </div>
      )}
      {loading ? (
        <p role="status" className="rounded-md border border-app-border bg-app-surface p-4 text-app-text-secondary">{t('adminCommon.loading')}</p>
      ) : error ? null : users.length === 0 ? (
        <p className="rounded-md border border-app-border bg-app-surface p-4 text-app-text-secondary">{t('adminCommon.empty')}</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-app-border bg-app-surface" role="region" aria-label={t('adminUsers.tableRegion')} tabIndex={0}>
          <table className="w-full min-w-[860px] border-collapse text-sm leading-5">
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 z-10 border-b border-app-border bg-app-surface-raised px-4 py-3 text-left font-semibold text-app-text-secondary">{t('adminUsers.columns.user')}</th>
                <th scope="col" className="border-b border-app-border px-4 py-3 text-left font-semibold text-app-text-secondary">{t('adminUsers.columns.email')}</th>
                <th scope="col" className="border-b border-app-border px-4 py-3 text-left font-semibold text-app-text-secondary">{t('adminUsers.columns.registered')}</th>
                <th scope="col" className="border-b border-app-border px-4 py-3 text-right font-semibold text-app-text-secondary tabular-nums">{t('adminUsers.columns.points')}</th>
                <th scope="col" className="border-b border-app-border px-4 py-3 text-right font-semibold text-app-text-secondary tabular-nums">{t('adminUsers.columns.wins')}</th>
                <th scope="col" className="border-b border-app-border px-4 py-3 text-right font-semibold text-app-text-secondary tabular-nums">{t('adminUsers.columns.games')}</th>
                <th scope="col" className="border-b border-app-border px-4 py-3 text-right font-semibold text-app-text-secondary tabular-nums">{t('adminUsers.columns.streak')}</th>
                <th scope="col" className="border-b border-app-border px-4 py-3 text-center font-semibold text-app-text-secondary">{t('adminUsers.columns.role')}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <th scope="row" className="sticky left-0 max-w-52 border-b border-app-border break-words bg-app-surface px-4 py-3 text-left font-semibold text-app-text">{user.username}</th>
                  <td className="max-w-64 border-b border-app-border break-all px-4 py-3 text-app-text-secondary">{user.email}</td>
                  <td className="whitespace-nowrap border-b border-app-border px-4 py-3 text-app-text-secondary">{user.created_at ? dateFormat.format(new Date(user.created_at)) : '—'}</td>
                  <td className="border-b border-app-border px-4 py-3 text-right text-app-text-secondary tabular-nums">{numberFormat.format(user.total_points)}</td>
                  <td className="border-b border-app-border px-4 py-3 text-right text-emerald-700 tabular-nums">{numberFormat.format(user.total_wins)}</td>
                  <td className="border-b border-app-border px-4 py-3 text-right text-app-text-secondary tabular-nums">{numberFormat.format(user.games_played)}</td>
                  <td className="border-b border-app-border px-4 py-3 text-right text-app-text-secondary tabular-nums"><span className="inline-flex items-center gap-1">{numberFormat.format(user.current_streak)}<Flame aria-hidden="true" size={14} className="text-emerald-700" /></span></td>
                  <td className="border-b border-app-border px-4 py-3 text-center">
                    <span className="inline-flex items-center gap-1 rounded-md border border-app-border px-2 py-0.5 text-xs text-app-text-secondary">{user.is_admin ? t('adminUsers.admin') : t('adminUsers.player')}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!loading && !error && (
        <nav className="flex flex-wrap items-center justify-between gap-3" aria-label={t('adminUsers.pagination')}>
          <span className="text-sm text-app-text-muted">{t('adminUsers.page', { page: numberFormat.format(page), pages: numberFormat.format(Math.max(1, pageCount)), count: totalUsers })}</span>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="min-h-11 rounded-md border border-app-border bg-app-surface-muted px-3 py-2 text-sm font-medium text-app-text transition-colors hover:bg-app-surface-raised focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>{t('adminCommon.previous')}</button>
            <button type="button" className="min-h-11 rounded-md border border-app-border bg-app-surface-muted px-3 py-2 text-sm font-medium text-app-text transition-colors hover:bg-app-surface-raised focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50" disabled={pageCount === 0 || page >= pageCount} onClick={() => onPageChange(page + 1)}>{t('adminCommon.next')}</button>
          </div>
        </nav>
      )}
    </section>
  );
};

export default AdminUsersTab;
