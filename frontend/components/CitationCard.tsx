"use client";

export type Citation = {
  chunk_id: string;
  episode_id: string;
  episode_title: string;
  episode_guest: string;
  episode_date: string;
  episode_link: string;
  episode_image: string;
  start_ts: string;
  start_seconds: number;
  text: string;
  score: number;
};

export default function CitationCard({
  c,
  idx,
  domId,
}: {
  c: Citation;
  idx: number;
  domId?: string;
}) {
  const href = c.episode_link || "#";
  const isDisabled = !c.episode_link;
  const snippet = c.text.length > 260 ? c.text.slice(0, 260).trim() + "…" : c.text;

  return (
    <a
      id={domId}
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={(e) => isDisabled && e.preventDefault()}
      className={`citation-card-root block rounded-xl border border-border bg-white p-3 shadow-soft transition hover:border-accent/50 hover:bg-parchmentAlt scroll-mt-24 ${
        isDisabled ? "opacity-60 cursor-not-allowed" : ""
      }`}
    >
      <div className="flex gap-3">
        {c.episode_image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={c.episode_image}
            alt=""
            className="w-14 h-14 rounded-md object-cover flex-none border border-border"
          />
        ) : (
          <div className="w-14 h-14 rounded-md bg-parchmentAlt grid place-items-center text-inkMuted text-xs flex-none border border-border">
            pod
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <span className="inline-block bg-accent text-white text-[10px] font-bold px-1.5 py-0.5 rounded leading-none mt-0.5">
              E{idx}
            </span>
            <h4 className="font-semibold text-[13.5px] leading-snug line-clamp-2 text-ink">
              {c.episode_title}
            </h4>
          </div>
          <div className="mt-1 text-[11.5px] text-inkMuted flex flex-wrap gap-x-2">
            {c.episode_guest && <span>{c.episode_guest}</span>}
            {c.episode_date && <span>· {c.episode_date}</span>}
            <span>· {c.start_ts}</span>
          </div>
        </div>
      </div>
      <p className="mt-2 text-[12.5px] text-ink/80 leading-snug line-clamp-3">
        {snippet}
      </p>
    </a>
  );
}
