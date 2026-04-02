export function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function statusTone(status: string) {
  const value = status.toLowerCase();

  if (value === "failed") {
    return "bg-rose-100 text-rose-800";
  }

  if (value === "queued" || value === "ready") {
    return "bg-sky-100 text-sky-800";
  }

  if (value === "done" || value === "completed") {
    return "bg-emerald-100 text-emerald-800";
  }

  if (value === "in_progress" || value === "active" || value === "running" || value === "waiting_human") {
    return "bg-amber-100 text-amber-900";
  }

  return "bg-slate-200 text-slate-700";
}

export function priorityTone(priority: string) {
  const value = priority.toLowerCase();

  if (value === "high") {
    return "bg-rose-100 text-rose-800";
  }

  if (value === "medium") {
    return "bg-sky-100 text-sky-800";
  }

  return "bg-stone-200 text-stone-700";
}
