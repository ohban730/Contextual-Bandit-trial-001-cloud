const suggestUrl = CONFIG.SUGGEST_URL;

async function fetchSuggestion(category) {
    const requestUrl = new URL(suggestUrl);
    if (category) {
        requestUrl.searchParams.set('category', category);
    }
    const resp = await fetch(requestUrl);

    if (!resp.ok) {
        const error = new Error(`提案の取得に失敗しました（status: ${resp.status}）`);

        try {
            const body = await resp.json();
            error.userMessage = body.error;
        } catch {
            // JSON でなければ、何もしない（userMessage なし → main.js で固定の文章を出す）
        }
        throw error;
    }

    const json = await resp.json();
    return json;
}