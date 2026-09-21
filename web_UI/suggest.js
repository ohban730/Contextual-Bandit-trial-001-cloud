const Suggest = (function () {
    const url = CONFIG.SUGGEST_URL;

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
            let recommendation = json.last_video_title;
            const p = document.querySelector('#recommendations');
            p.innerHTML = recommendation;
            console.log(recommendation);
        } else {
            console.log('Error: ' + resp.status);
            console.log('取得に失敗しました');
        }
    }

    return { main };  // 外に出したいものだけ返す
})();