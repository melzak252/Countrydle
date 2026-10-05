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
  const { t, i18n } = useTranslation();
  const [inputSearch, setInputSearch] = useState(search);
  const locale = i18n.language.startsWith('pl') ? 'pl-PL' : 'en-US';
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
    <section className="min-w-0 space-y-4" aria-labelledby="admin-page-title">
      <div className="admin-toolbar flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0 flex-1 sm:max-w-xl">
          <label htmlFor="admin-users-search" className="mb-1 block text-sm font-medium text-slate-300">{t('adminUsers.searchLabel')}</label>
          <div className="relative">
            <Search aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              id="admin-users-search"
              type="search"
              value={inputSearch}
              onChange={(event) => setInputSearch(event.target.value)}
              placeholder={t('adminUsers.searchPlaceholder')}
              className="admin-control admin-control-with-icon"
            />
          </div>
        </div>
        <button type="button" className="admin-button" onClick={onRefresh} disabled={loading}>
          <RefreshCw aria-hidden="true" size={15} />
          {loading ? t('adminCommon.updating') : t('adminCommon.refresh')}
        </button>
      </div>
      {error && !queryPending && (
        <div role="alert" className="admin-panel flex flex-wrap items-center justify-between gap-3 border-rose-400/40 text-rose-200">
          <span>{t(error)}</span>
          <button type="button" className="admin-button" onClick={onRefresh} disabled={loading}>{t('adminCommon.retry')}</button>
        </div>
      )}
      {loading ? (
        <p role="status" className="admin-panel">{t('adminCommon.loading')}</p>
      ) : error ? null : users.length === 0 ? (
        <p className="admin-panel admin-muted">{t('adminCommon.empty')}</p>
      ) : (
        <div className="admin-table overflow-x-auto" role="region" aria-label={t('adminUsers.tableRegion')} tabIndex={0}>
          <table className="w-full min-w-[860px] text-sm">
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 z-10 bg-obsidian-850 px-4 py-3 text-left">{t('adminUsers.columns.user')}</th>
                <th scope="col" className="px-4 py-3 text-left">{t('adminUsers.columns.email')}</th>
                <th scope="col" className="px-4 py-3 text-left">{t('adminUsers.columns.registered')}</th>
                <th scope="col" className="admin-number px-4 py-3">{t('adminUsers.columns.points')}</th>
                <th scope="col" className="admin-number px-4 py-3">{t('adminUsers.columns.wins')}</th>
                <th scope="col" className="admin-number px-4 py-3">{t('adminUsers.columns.games')}</th>
                <th scope="col" className="admin-number px-4 py-3">{t('adminUsers.columns.streak')}</th>
                <th scope="col" className="px-4 py-3 text-center">{t('adminUsers.columns.role')}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <th scope="row" className="sticky left-0 max-w-52 break-words bg-obsidian-900 px-4 py-3 text-left font-semibold text-sand-100">{user.username}</th>
                  <td className="max-w-64 break-all px-4 py-3 text-slate-300">{user.email}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-300">{user.created_at ? dateFormat.format(new Date(user.created_at)) : '—'}</td>
                  <td className="admin-number px-4 py-3 text-right">{numberFormat.format(user.total_points)}</td>
                  <td className="admin-number px-4 py-3 text-right text-emerald-300">{numberFormat.format(user.total_wins)}</td>
                  <td className="admin-number px-4 py-3 text-right">{numberFormat.format(user.games_played)}</td>
                  <td className="admin-number px-4 py-3 text-right"><span className="inline-flex items-center gap-1">{numberFormat.format(user.current_streak)}<Flame aria-hidden="true" size={14} className="text-emerald-300" /></span></td>
                  <td className="px-4 py-3 text-center">
                    <span className="admin-badge">{user.is_admin ? t('adminUsers.admin') : t('adminUsers.player')}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!loading && !error && (
        <nav className="admin-pager flex flex-wrap items-center justify-between gap-3" aria-label={t('adminUsers.pagination')}>
          <span className="admin-meta">{t('adminUsers.page', { page: numberFormat.format(page), pages: numberFormat.format(Math.max(1, pageCount)), count: totalUsers })}</span>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="admin-button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>{t('adminCommon.previous')}</button>
            <button type="button" className="admin-button" disabled={pageCount === 0 || page >= pageCount} onClick={() => onPageChange(page + 1)}>{t('adminCommon.next')}</button>
          </div>
        </nav>
      )}
    </section>
  );
};

export default AdminUsersTab;
