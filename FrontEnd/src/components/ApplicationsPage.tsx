import { useCallback, useEffect, useState } from 'react';
import { KanbanSquare, Trash2 } from 'lucide-react';
import {
  getApplications,
  removeApplication,
  setApplicationStatus,
  TrackedApplication,
} from '../lib/applicationsApi';

const STATUS_LABELS: Record<string, string> = {
  bookmarked: '已收藏',
  applied: '已投递',
  replied: '有回复',
  interview: '面试中',
  offer: '已拿 Offer',
  rejected: '已拒绝',
};

const STATUS_COLORS: Record<string, string> = {
  bookmarked: 'bg-gray-100 text-gray-700',
  applied: 'bg-blue-50 text-blue-700',
  replied: 'bg-amber-50 text-amber-700',
  interview: 'bg-purple-50 text-purple-700',
  offer: 'bg-green-50 text-green-700',
  rejected: 'bg-red-50 text-red-600',
};

export default function ApplicationsPage() {
  const [items, setItems] = useState<TrackedApplication[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getApplications();
      setItems(data.applications);
      setStatuses(data.statuses);
      setNotes(
        Object.fromEntries(data.applications.map(item => [item.job_id, item.note]))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const changeStatus = async (jobId: string, status: string) => {
    try {
      await setApplicationStatus(jobId, status, notes[jobId] ?? '');
      setItems(prev => prev.map(item => (item.job_id === jobId ? { ...item, status } : item)));
    } catch (e) {
      setError(e instanceof Error ? e.message : '更新失败');
    }
  };

  const saveNote = async (jobId: string) => {
    const item = items.find(i => i.job_id === jobId);
    if (!item) return;
    try {
      await setApplicationStatus(jobId, item.status, notes[jobId] ?? '');
    } catch (e) {
      setError(e instanceof Error ? e.message : '备注保存失败');
    }
  };

  const remove = async (jobId: string) => {
    try {
      await removeApplication(jobId);
      setItems(prev => prev.filter(item => item.job_id !== jobId));
    } catch (e) {
      setError(e instanceof Error ? e.message : '移除失败');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center space-x-3 mb-6">
        <KanbanSquare className="w-6 h-6 text-blue-600" />
        <h1 className="text-2xl font-semibold text-gray-900">投递看板</h1>
        <span className="text-sm text-gray-500">{items.length} 个在跟踪的岗位</span>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
          <button className="ml-3 underline" onClick={load}>重试</button>
        </div>
      )}

      {loading ? (
        <div className="py-20 text-center text-gray-500">加载中…</div>
      ) : items.length === 0 ? (
        <div className="py-20 text-center text-gray-500">
          还没有跟踪任何岗位。在岗位匹配页挑一个开始吧。
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">岗位</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">公司</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">备注</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">更新于</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map(item => (
                <tr key={item.job_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-900">{item.job_title || item.job_id}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{item.company_name}</td>
                  <td className="px-4 py-3">
                    <select
                      value={item.status}
                      onChange={e => changeStatus(item.job_id, e.target.value)}
                      className={`text-xs rounded-full px-2.5 py-1 border-0 cursor-pointer ${STATUS_COLORS[item.status] ?? 'bg-gray-100 text-gray-700'}`}
                    >
                      {statuses.map(s => (
                        <option key={s} value={s}>{STATUS_LABELS[s] ?? s}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <input
                      value={notes[item.job_id] ?? ''}
                      onChange={e => setNotes(prev => ({ ...prev, [item.job_id]: e.target.value }))}
                      onBlur={() => saveNote(item.job_id)}
                      placeholder="随手记一句…"
                      className="w-full text-sm bg-transparent border-b border-transparent hover:border-gray-200 focus:border-blue-400 outline-none py-1"
                    />
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">{item.updated_at?.slice(0, 10)}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => remove(item.job_id)}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                      title="移出看板"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
