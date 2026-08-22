import { beginScreenLoad, endScreenLoad, setScreenLoadProgress } from "./screen-loader.js";
import { $, escapeHtml, finishLoadingProgress, setLoadingProgress } from "./utils.js";

export function createSlugDocumentEditor({
  apiBase,
  ids,
  copy,
  defaultPdfFilename,
  api,
  showError,
  showToast,
}) {
  let items = [];
  let selectedSlug = "";
  let selectedHasPdf = false;
  let selectedPdfFilename = defaultPdfFilename;

  function pdfUrl(slug, { download = false } = {}) {
    const params = new URLSearchParams();
    if (download) params.set("download", "1");
    else params.set("ts", String(Date.now()));
    const query = params.toString();
    return `${apiBase}/${encodeURIComponent(slug)}/pdf${query ? `?${query}` : ""}`;
  }

  function updatePdfPreview({ slug, hasPdf, pdfFilename }) {
    selectedHasPdf = Boolean(hasPdf);
    selectedPdfFilename = pdfFilename || defaultPdfFilename;

    const download = $(ids.downloadPdf);
    const openPdf = $(ids.openPdf);
    if (download) {
      download.href = slug ? pdfUrl(slug, { download: true }) : "#";
      download.download = selectedPdfFilename;
      download.hidden = !selectedHasPdf;
    }
    if (openPdf) {
      openPdf.href = slug && selectedHasPdf ? pdfUrl(slug) : "#";
      openPdf.hidden = !selectedHasPdf;
    }

    const pdfFrame = $(ids.pdfFrame);
    const pdfMissing = $(ids.pdfMissing);
    const renderBtn = $(ids.renderBtn);

    if (renderBtn) renderBtn.disabled = !slug;

    if (selectedHasPdf && slug && pdfFrame) {
      pdfFrame.hidden = false;
      pdfFrame.src = pdfUrl(slug);
      if (pdfMissing) pdfMissing.hidden = true;
    } else {
      if (pdfFrame) {
        pdfFrame.removeAttribute("src");
        pdfFrame.hidden = true;
      }
      if (pdfMissing) pdfMissing.hidden = false;
    }
  }

  function renderList() {
    const list = $(ids.list);
    if (!list) return;

    if (!items.length) {
      list.innerHTML = `<li class="apply-master-empty">${copy.emptyList}</li>`;
      return;
    }

    list.innerHTML = items.map((item) => {
      const label = (item.label || item.slug).trim();
      const active = item.slug === selectedSlug ? " apply-master-item--active" : "";
      const pdfBadge = item.has_pdf
        ? '<span class="apply-master-item-badge apply-master-item-badge--pdf">PDF</span>'
        : "";
      return `<li><button type="button" class="apply-master-item${active}" data-slug="${escapeHtml(item.slug)}"><span class="apply-master-item-label">${escapeHtml(label)}${pdfBadge}</span><span class="apply-master-item-slug">${escapeHtml(item.slug)}</span></button></li>`;
    }).join("");
  }

  function clear() {
    selectedSlug = "";
    selectedHasPdf = false;
    selectedPdfFilename = defaultPdfFilename;
    $(ids.slug).value = "";
    $(ids.label).value = "";
    $(ids.content).value = "";
    $(ids.updated).textContent = "";
    updatePdfPreview({ slug: "", hasPdf: false });
    const pdfMissing = $(ids.pdfMissing);
    if (pdfMissing) pdfMissing.hidden = false;
    renderList();
  }

  async function loadDetail(slug) {
    selectedSlug = slug;
    renderList();
    setLoadingProgress(20);
    try {
      const detail = await api(`${apiBase}/${encodeURIComponent(slug)}`);
      $(ids.slug).value = detail.slug || slug;
      $(ids.label).value = detail.label || "";
      $(ids.content).value = detail.content || "";
      const updatedParts = [];
      if (detail.updated_at) updatedParts.push(`Updated ${detail.updated_at}`);
      if (detail.pdf_updated_at) updatedParts.push(`PDF ${detail.pdf_updated_at}`);
      $(ids.updated).textContent = updatedParts.join(" · ");
      updatePdfPreview({
        slug: detail.slug || slug,
        hasPdf: detail.has_pdf,
        pdfFilename: detail.pdf_filename,
      });
    } finally {
      finishLoadingProgress();
    }
  }

  async function persist() {
    const slug = $(ids.slug).value.trim();
    const content = $(ids.content).value;
    if (!slug) {
      throw new Error(copy.slugRequired);
    }
    if (!content.trim()) {
      throw new Error(copy.contentRequired);
    }

    const saved = await api(`${apiBase}/${encodeURIComponent(slug)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content,
        label: $(ids.label).value.trim(),
      }),
    });
    selectedSlug = saved.slug || slug;
    const listing = await api(apiBase);
    items = listing.items || [];
    renderList();
    $(ids.updated).textContent = saved.updated_at
      ? `Updated ${saved.updated_at}`
      : "";
    return saved;
  }

  async function refreshDetail(slug = selectedSlug) {
    if (!slug) return null;
    const detail = await api(`${apiBase}/${encodeURIComponent(slug)}`);
    const updatedParts = [];
    if (detail.updated_at) updatedParts.push(`Updated ${detail.updated_at}`);
    if (detail.pdf_updated_at) updatedParts.push(`PDF ${detail.pdf_updated_at}`);
    $(ids.updated).textContent = updatedParts.join(" · ");
    updatePdfPreview({
      slug: detail.slug || slug,
      hasPdf: detail.has_pdf,
      pdfFilename: detail.pdf_filename,
    });
    return detail;
  }

  async function rerenderPdf() {
    const slug = $(ids.slug).value.trim() || selectedSlug;
    if (!slug) {
      showError(copy.renderRequired);
      return;
    }

    const btn = $(ids.renderBtn);
    const saveBtn = $(ids.saveBtn);
    btn.disabled = true;
    if (saveBtn) saveBtn.disabled = true;
    showError("");
    beginScreenLoad("Rendering PDF…");
    setScreenLoadProgress(15);
    const tick = window.setInterval(() => setScreenLoadProgress(88), 800);
    try {
      setScreenLoadProgress(20);
      await persist();
      setScreenLoadProgress(35);
      const result = await api(
        `${apiBase}/${encodeURIComponent(selectedSlug)}/render`,
        { method: "POST" },
      );
      setScreenLoadProgress(92);
      if (!result.ok) {
        throw new Error(result.error || result.log || "Render failed");
      }
      showToast("PDF re-rendered");
      updatePdfPreview({
        slug: selectedSlug,
        hasPdf: Boolean(result.pdf_stored),
        pdfFilename: result.pdf_filename,
      });
      setScreenLoadProgress(96);
      await refreshDetail(selectedSlug);
    } catch (err) {
      showError(err.message || copy.renderFailed);
    } finally {
      window.clearInterval(tick);
      endScreenLoad();
      btn.disabled = false;
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  async function save() {
    showError("");
    const btn = $(ids.saveBtn);
    btn.disabled = true;
    try {
      await persist();
      await refreshDetail(selectedSlug);
      showToast(`Saved ${selectedSlug}`);
    } catch (err) {
      showError(err.message || copy.saveFailed);
    } finally {
      btn.disabled = false;
    }
  }

  function startNew() {
    clear();
    $(ids.slug).focus();
  }

  function bind() {
    $(ids.saveBtn)?.addEventListener("click", save);
    $(ids.renderBtn)?.addEventListener("click", rerenderPdf);
    $(ids.newBtn)?.addEventListener("click", startNew);
    $(ids.list)?.addEventListener("click", (e) => {
      const btn = e.target.closest(".apply-master-item");
      if (!btn) return;
      loadDetail(btn.dataset.slug);
    });
  }

  function replaceItems(nextItems) {
    items = nextItems || [];
    renderList();
  }

  async function loadFirstIfNeeded() {
    if (items.length && !selectedSlug) {
      await loadDetail(items[0].slug);
    }
  }

  function resyncPreview() {
    if (!selectedSlug) return;
    updatePdfPreview({
      slug: selectedSlug,
      hasPdf: selectedHasPdf,
      pdfFilename: selectedPdfFilename,
    });
  }

  function reset() {
    items = [];
    clear();
  }

  return {
    replaceItems,
    loadFirstIfNeeded,
    resyncPreview,
    reset,
    bind,
  };
}
