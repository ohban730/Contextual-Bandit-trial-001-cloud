const Feedback = (function () {
    const url = CONFIG.FEEDBACK_URL;

    async function main(label) {
        const suggestionId = Suggest.takeSuggestionId();
        if (!suggestionId) {
            document.querySelector('#feedback').innerHTML = '先におすすめ動画をリクエストしてください';
            return;
        }
        const resp = await fetch(url + `?label=${label}&suggestion_id=${suggestionId}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: null
            }
        );
        if (resp.status == 200) {
            const json = await resp.json();
            let channel_name = json.channel_name;
            let label = json.label;
            const p = document.querySelector('#feedback');
            p.innerHTML = channel_name + 'に対して' + label + 'のフィードバックを送信しました';
            console.log(channel_name);
        } else {
            const p = document.querySelector('#feedback');
            p.innerHTML = 'フィードバックの送信に失敗しました';
            console.log('Error: ' + resp.status);
            console.log('取得に失敗しました');
        }
    }

    return { main };
})();