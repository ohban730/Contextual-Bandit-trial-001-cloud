const Suggest = (function () {
    const url = CONFIG.SUGGEST_URL;
    let currentSuggestionId = null;  // 表示中の提案。feedbackはこのIDに対して送る

    async function main() {
        const resp = await fetch(url, {
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
            const p = document.querySelector('#recommendations');
            p.innerHTML = recommendation;
            console.log(recommendation);
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