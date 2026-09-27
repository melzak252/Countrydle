import React from 'react';
import { Search, Flame } from 'lucide-react';

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
  onSearchChange: (search: string) => void;
  onPageChange: (page: number) => void;
}

export const AdminUsersTab: React.FC<AdminUsersTabProps> = ({
  users,
  totalUsers,
  search,
  page,
  isLoading,
  onSearchChange,
  onPageChange,
}) => {
  return (
    <div className="space-y-6 animate-message">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sand-100/55" size={16} />
          <input
            type="text"
            aria-label="Search users by username or email"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search username or email..."
            className="w-full pl-10 pr-4 py-2.5 bg-obsidian-900 border border-white/10 rounded-sm text-sand-100 text-xs md:text-sm focus:outline-none focus:border-emerald-400 transition-colors"
          />
        </div>
        <div className="text-xs text-sand-100/65 font-mono">
          Total registered: {totalUsers} users
        </div>
      </div>

      <div className="bg-obsidian-900 border border-white/10 rounded-sm overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-xs md:text-sm">
          <thead className="bg-white/[0.03] text-sand-100/65 border-b border-white/10">
            <tr>
              <th className="px-5 py-3 font-semibold">User</th>
              <th className="px-5 py-3 font-semibold">Email</th>
              <th className="px-5 py-3 font-semibold">Registered</th>
              <th className="px-5 py-3 font-semibold text-right">Points</th>
              <th className="px-5 py-3 font-semibold text-right">Wins</th>
              <th className="px-5 py-3 font-semibold text-right">Games</th>
              <th className="px-5 py-3 font-semibold text-right">Streak</th>
              <th className="px-5 py-3 font-semibold text-center">Role</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {isLoading ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-xs font-mono text-zinc-500">
                  Loading user records...
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-xs font-mono text-zinc-500">
                  No users found.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="hover:bg-white/[0.03] transition-colors">
                  <td className="px-5 py-3.5 font-semibold text-sand-100">{u.username}</td>
                  <td className="px-5 py-3.5 text-sand-100/65 font-mono text-xs">{u.email}</td>
                  <td className="px-5 py-3.5 text-sand-100/55 font-mono text-xs">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono font-semibold text-sand-100/80">{u.total_points}</td>
                  <td className="px-5 py-3.5 text-right font-mono font-semibold text-emerald-300">{u.total_wins}</td>
                  <td className="px-5 py-3.5 text-right font-mono text-sand-100/80">{u.games_played}</td>
                  <td className="px-5 py-3.5 text-right font-mono text-sand-100/80">
                    <span className="inline-flex items-center gap-1">
                      <span>{u.current_streak}</span>
                      <Flame size={12} className="text-emerald-300" />
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-center">
                    {u.is_admin ? (
                      <span className="text-emerald-300 text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30">
                        ADMIN
                      </span>
                    ) : (
                      <span className="text-sand-100/55 text-xs">Player</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex flex-wrap gap-3 justify-between items-center text-xs text-sand-100/65 font-mono">
        <span>Page {page}</span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1 || isLoading}
            onClick={() => onPageChange(Math.max(1, page - 1))}
            className="px-3 py-1.5 bg-obsidian-950 hover:bg-white/5 disabled:opacity-40 rounded-sm text-sand-100 font-medium border border-white/10"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={users.length < 25 || isLoading}
            onClick={() => onPageChange(page + 1)}
            className="px-3 py-1.5 bg-obsidian-950 hover:bg-white/5 disabled:opacity-40 rounded-sm text-sand-100 font-medium border border-white/10"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminUsersTab;
