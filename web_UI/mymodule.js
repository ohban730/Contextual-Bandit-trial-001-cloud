const readline = require('readline');

function prompt(msg) {
    const read = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });

    return new Promise((resolve, reject) => {
        read.question(msg, (answer) => {
            resolve(answer);
            read.close();
        });
    });
};

module.exports.prompt = prompt;