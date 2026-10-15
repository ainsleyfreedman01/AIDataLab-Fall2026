export const meta = {
  name: 'privacy-passages-extract',
  description: 'Extract verbatim data/student-privacy passages from 202 K-12 AI policy documents into JSON specs',
  phases: [{ title: 'Extract', detail: 'one Sonnet agent per batch of documents', model: 'sonnet' }],
}
const W = args.work
const RESULT = {
  type: 'object',
  properties: {
    rows: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          row: { type: 'integer' },
          spec_written: { type: 'boolean' },
          no_privacy: { type: 'boolean' },
          sections: { type: 'integer' },
          issues: { type: 'array', items: { type: 'string' } },
        },
        required: ['row', 'spec_written', 'no_privacy', 'sections', 'issues'],
      },
    },
  },
  required: ['rows'],
}
const pad = n => String(n).padStart(3, '0')
const base = `Working directory for this task: ${W}
First read ${W}\\GUIDE.md completely and follow it exactly. Also look at the three finished example PDFs the user made, to calibrate scope and style (read them, they are short):
- C:\\Users\\sukhr\\OneDrive\\Documents\\AI_Data_Lab_Readings\\FBISD_AI_Handbook_Privacy_Passages.pdf
- C:\\Users\\sukhr\\OneDrive\\Documents\\AI_Data_Lab_Readings\\PSJA_AI_Guidebook_Privacy_Passages.pdf
- C:\\Users\\sukhr\\Downloads\\Massachusetts_AI_Guidance_Privacy_Passages.pdf
`
phase('Extract')
const jobs = args.batches.map(rows => ({ kind: 'batch', rows }))
for (const [k, range] of [[1, '1-136'], [2, '137-272'], [3, '273-408']]) jobs.push({ kind: 'il', k, range })

const results = await parallel(jobs.map(job => () => {
  if (job.kind === 'batch') {
    const files = job.rows.map(r => `${W}\\text\\${pad(r)}.txt -> write ${W}\\specs\\${pad(r)}.json`).join('\n')
    return agent(`${base}
Your assigned rows (process each one fully, one at a time):
${files}

Return one entry per assigned row.`, { label: `rows ${job.rows.join(',')}`, phase: 'Extract', schema: RESULT, model: 'sonnet' })
  }
  return agent(`${base}
Your assignment: row 100 (Illinois State Board of Education, "Guidance on Artificial Intelligence", 408 PDF pages) is split across three agents. You cover ONLY PDF pages ${job.range} of ${W}\\text\\100.txt (text between the "=== PDF page N of 408 ===" markers for those pages; use Grep with line numbers to find the marker lines, then Read by offset). Write ${W}\\specs\\100_p${job.k}.json in the normal spec shape containing only sections from your pages, in page order. Use file_stem "Illinois_AI_Guidance", doc_title "Illinois AI Guidance". Determine whether printed page numbers are reliably identifiable; set page_mode accordingly and mention in issues which convention you used and why. Because this document is long, rely on grep plus reading each hit's whole section; still be inclusive per the guide.

Return a single entry with row 100.`, { label: `Illinois pages ${job.range}`, phase: 'Extract', schema: RESULT, model: 'sonnet' })
}))
const flat = results.filter(Boolean).flatMap(r => r.rows)
const missing = jobs.filter((j, i) => !results[i]).map(j => j.rows || `IL part ${j.k}`)
if (missing.length) log(`Agents that failed: ${JSON.stringify(missing)}`)
return { rows: flat, failed: missing }