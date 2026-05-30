import type { XMemClient } from "../client.ts"
import type { XMemOpenClawConfig } from "../config.ts"

export function buildRecallHandler(client: XMemClient, cfg: XMemOpenClawConfig) {
	return async (event: Record<string, unknown>) => {
		const prompt = String(event.prompt || event.input || event.message || "")
		if (!prompt.trim()) return
		const results = await client.search(prompt, cfg.maxRecallResults)
		if (!results.length) return
		return {
			additionalContext: `<xmem-context>\n${results.map((r, i) => `${i + 1}. ${r.content || ""}`).join("\n\n")}\n</xmem-context>`,
		}
	}
}
