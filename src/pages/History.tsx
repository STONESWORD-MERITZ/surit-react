import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  listDisclosureResults,
  deleteDisclosureResult,
  type SavedResult,
} from "../lib/disclosureStorage";

export default function History() {
  const [items, setItems] = useState<SavedResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    try {
      setItems(await listDisclosureResults());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "조회 실패");
    }
  }

  useEffect(() => {
    listDisclosureResults()
      .then((data) => setItems(data))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "조회 실패"));
  }, []);

  async function onDelete(id: string) {
    if (!window.confirm("이 분석 결과를 삭제할까요?")) return;
    try {
      await deleteDisclosureResult(id);
      await reload();
    } catch (e: unknown) {
      alert(`삭제 실패: ${e instanceof Error ? e.message : "오류"}`);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-extrabold text-gray-950">내 점검 기록</h1>
      <p className="mt-1 text-sm text-gray-500">
        저장한 분석 결과만 보여드립니다. 본인 외에는 볼 수 없어요.
      </p>

      {error && <p className="mt-6 text-sm text-red-600">{error}</p>}

      {items === null && !error && (
        <p className="mt-10 text-sm text-gray-400">불러오는 중…</p>
      )}

      {items && items.length === 0 && (
        <div className="mt-10 rounded-2xl border border-gray-200 bg-white px-6 py-10 text-center">
          <p className="text-sm text-gray-500">아직 저장한 분석 결과가 없어요.</p>
          <Link
            to="/disclosure?mode=agent"
            className="mt-4 inline-flex rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white"
          >
            분석 시작
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <ul className="mt-8 space-y-3">
          {items.map((it) => (
            <li key={it.id} className="rounded-2xl border border-gray-200 bg-white px-5 py-4">
              <div className="flex items-start justify-between gap-3">
                <Link to={`/history/${it.id}`} className="block min-w-0">
                  <p className="truncate text-[15px] font-bold text-gray-900">
                    {it.title || `${it.ref_date} 점검`}
                  </p>
                  <p className="mt-1 text-xs text-gray-500">
                    {it.product_type} · 기준일 {it.ref_date} · 저장{" "}
                    {new Date(it.created_at).toLocaleString("ko-KR")}
                  </p>
                  {it.verdict && (
                    <p className="mt-1 text-xs text-gray-400">추천 심사: {it.verdict}</p>
                  )}
                </Link>
                <button
                  onClick={() => onDelete(it.id)}
                  className="shrink-0 text-xs font-bold text-gray-400 hover:text-red-600"
                >
                  삭제
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
