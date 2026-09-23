const Suggest = (function () {
    const url = CONFIG.SUGGEST_URL;
    let currentSuggestionId = null;  // 表示中の提案。feedbackはこのIDに対して送る

    async function main(category) {
        const requestUrl = new URL(url);
        if (category) {
            requestUrl.searchParams.set('category', category);
        }
        const resp = await fetch(requestUrl, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            },
            body: null
        }
        );
        if (resp.status == 200) {
            const json = await resp.json();
            currentSuggestionId = json.suggestion_id;
            let recommendation = json.last_video_title;
            let dominant_category_name = json.dominant_category_name ?? '不明';
            const reco_p = document.querySelector('#recommendations');
            reco_p.textContent = recommendation;
            const genre_p = document.querySelector('#genre');
            genre_p.textContent = dominant_category_name;
            console.log(recommendation);
            console.log('カテゴリ：'+ dominant_category_name);
        } else {
            console.log('Error: ' + resp.status);
            console.log('取得に失敗しました');
        }
    }

    function takeSuggestionId() {
        const id = currentSuggestionId;
        currentSuggestionId = null;  // 同じ提案に二重で評価しないよう、一度渡したら消す
        return id;
    }

    return { main, takeSuggestionId };  // 外に出したいものだけ返す
})();