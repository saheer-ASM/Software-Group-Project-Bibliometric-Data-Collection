const keyFor = (userId) => `scholarMetricsLibrary:${userId || 'guest'}`;

const emptyLibrary = () => ({ savedAuthors: [], savedPapers: [], recentAuthors: [], collections: [] });

export function getLibrary(userId) {
  try {
    return { ...emptyLibrary(), ...JSON.parse(localStorage.getItem(keyFor(userId))) };
  } catch (_) {
    return emptyLibrary();
  }
}

export function saveLibrary(userId, library) {
  localStorage.setItem(keyFor(userId), JSON.stringify(library));
  window.dispatchEvent(new CustomEvent('research-library-changed', { detail: library }));
  return library;
}

export function updateLibrary(userId, updater) {
  return saveLibrary(userId, updater(getLibrary(userId)));
}

export function recordRecentAuthor(userId, author) {
  if (!author?.id) return;
  updateLibrary(userId, (library) => ({
    ...library,
    recentAuthors: [
      { id: author.id, name: author.name, viewedAt: new Date().toISOString() },
      ...library.recentAuthors.filter((item) => item.id !== author.id)
    ].slice(0, 10)
  }));
}

export function toggleSavedAuthor(userId, author) {
  return updateLibrary(userId, (library) => ({
    ...library,
    savedAuthors: library.savedAuthors.some((item) => item.id === author.id)
      ? library.savedAuthors.filter((item) => item.id !== author.id)
      : [{ ...author, savedAt: new Date().toISOString() }, ...library.savedAuthors]
  }));
}

export function toggleSavedPaper(userId, paper) {
  return updateLibrary(userId, (library) => ({
    ...library,
    savedPapers: library.savedPapers.some((item) => item.id === paper.id)
      ? library.savedPapers.filter((item) => item.id !== paper.id)
      : [{ ...paper, savedAt: new Date().toISOString() }, ...library.savedPapers]
  }));
}

export function savePaperToCollection(userId, paper, collectionId, newCollectionName = '') {
  return updateLibrary(userId, (library) => {
    let collections = library.collections;
    let targetId = collectionId;
    const name = newCollectionName.trim();
    if (name) {
      targetId = `collection-${Date.now()}`;
      collections = [...collections, { id: targetId, name, paperIds: [] }];
    }
    collections = collections.map((collection) => ({
      ...collection,
      paperIds: collection.id === targetId
        ? [...new Set([...collection.paperIds, paper.id])]
        : collection.paperIds.filter((id) => id !== paper.id)
    }));
    return {
      ...library,
      collections,
      savedPapers: library.savedPapers.some((item) => item.id === paper.id)
        ? library.savedPapers
        : [{ ...paper, savedAt: new Date().toISOString() }, ...library.savedPapers]
    };
  });
}

export function downloadAuthorPdf(data) {
  const clean = (value) => String(value ?? '').replace(/[^\x20-\x7E]/g, ' ').replace(/[()\\]/g, '\\$&');
  const wrap = (text, width = 72) => {
    const words = clean(text).split(/\s+/); const lines = []; let line = '';
    words.forEach((word) => { if (`${line} ${word}`.trim().length > width) { if (line) lines.push(line); line = word; } else line = `${line} ${word}`.trim(); });
    if (line) lines.push(line); return lines;
  };
  const text = (x, y, size, value, color = '0.04 0.15 0.29') => `${color} rg BT /F1 ${size} Tf ${x} ${y} Td (${clean(value)}) Tj ET`;
  const rect = (x, y, w, h, color) => `${color} rg ${x} ${y} ${w} ${h} re f`;
  const line = (x1, y1, x2, y2, color = '0.86 0.90 0.94') => `${color} RG ${x1} ${y1} m ${x2} ${y2} l S`;
  const papers = data.publications || [];
  const pageCount = Math.max(1, Math.ceil(papers.length / 8));
  const streams = Array.from({ length: pageCount }, (_, pageIndex) => {
    const commands = [rect(0, 0, 612, 842, '0.97 0.98 0.99'), rect(0, 742, 612, 100, '0.03 0.15 0.29'), rect(0, 736, 612, 6, '0.78 0.60 0.24')];
    commands.push(text(42, 803, 20, 'ScholarMetrics', '1 1 1'), text(42, 780, 10, 'AUTHOR SUMMARY REPORT', '0.90 0.72 0.31'));
    commands.push(text(500, 803, 9, `Page ${pageIndex + 1} of ${pageCount}`, '0.82 0.88 0.92'));
    if (pageIndex === 0) {
      commands.push(text(42, 698, 20, data.author), text(42, 675, 10, `Research profile  |  ${data.authorId || 'ID unavailable'}`, '0.33 0.42 0.53'));
      const metrics = [['PUBLICATIONS', data.totalPublications], ['CITATIONS', data.totalCitations], ['H-INDEX', data.hIndex], ['NM-INDEX', data.nmIndex], ['C-SCORE', Number(data.cScore || 0).toFixed(3)], ['ADJUSTED CITATIONS', Number(data.totalAdjustedCitations || 0).toFixed(3)]];
      metrics.forEach(([label, value], index) => { const x = 42 + (index % 3) * 176; const y = 598 - Math.floor(index / 3) * 86; commands.push(rect(x, y, 160, 68, '0.92 0.95 0.97'), text(x + 14, y + 43, 8, label, '0.33 0.42 0.53'), text(x + 14, y + 17, 17, value)); });
      commands.push(text(42, 466, 13, 'Publication overview'), text(42, 448, 9, `${papers.length} publication${papers.length === 1 ? '' : 's'} included in this report`, '0.33 0.42 0.53'), line(42, 436, 570, 436));
    } else {
      commands.push(text(42, 700, 15, 'Publication record'), text(42, 679, 9, data.author, '0.33 0.42 0.53'), line(42, 665, 570, 665));
    }
    let y = pageIndex === 0 ? 408 : 635;
    papers.slice(pageIndex * 8, pageIndex * 8 + 8).forEach((paper, localIndex) => {
      const number = pageIndex * 8 + localIndex + 1;
      commands.push(rect(42, y - 58, 528, 66, '1 1 1'), text(55, y - 10, 8, `PAPER ${String(number).padStart(2, '0')}  |  ${paper.publishedYear || 'YEAR UNAVAILABLE'}`, '0.66 0.46 0.12'));
      wrap(paper.title, 78).slice(0, 2).forEach((titleLine, index) => commands.push(text(55, y - 29 - index * 13, 9, titleLine)));
      y -= 77;
    });
    commands.push(line(42, 42, 570, 42), text(42, 25, 8, `Generated ${new Date().toLocaleString()}  |  ScholarMetrics`, '0.43 0.50 0.58'));
    return commands.join('\n');
  });
  const fontId = 3 + streams.length * 2;
  const pageIds = streams.map((_, index) => 3 + index * 2);
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${streams.length} >>`];
  streams.forEach((stream, index) => { const pageId = pageIds[index]; objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 ${fontId} 0 R >> >> /Contents ${pageId + 1} 0 R >>`, `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`); });
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');
  let pdf = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(pdf.length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  offsets.slice(1).forEach((offset) => { pdf += `${String(offset).padStart(10, '0')} 00000 n \n`; });
  pdf += `trailer << /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([pdf], { type: 'application/pdf' }));
  link.download = `${clean(data.author).replace(/\s+/g, '-') || 'author'}-summary.pdf`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
