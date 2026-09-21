// これをコピーして config.js を作り、実際のCloud Run functionsのURLを設定する。
// config.js は .gitignore 対象（--allow-unauthenticated なのでURLが漏れると
// 誰でも/feedbackを叩けてしまうため）。
const CONFIG = {
    SUGGEST_URL: "<suggestのURL>",
    FEEDBACK_URL: "<feedbackのURL>",
};
