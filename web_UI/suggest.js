const suggestUrl = CONFIG.SUGGEST_URL;

async function fetchSuggestion(category) {
    const requestUrl = new URL(suggestUrl);
    if (category) {
        requestUrl.searchParams.set('category', category);
    }
    const resp = await fetch(requestUrl);

    if (!resp.ok) {
        throw new Error(`提案の取得に失敗しました（status: ${resp.status}）`);
    }

    const json = await resp.json();
    return json;
}