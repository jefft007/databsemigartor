const { FormData } = require('formdata-node');
const { File } = require('formdata-node');

const fd = new FormData();
fd.append('file', new File(['hello'], 'hello.txt'));

const fd2 = new FormData();
for (const [k, v] of fd.entries()) {
    fd2.append(k, v);
}

const fd3 = new FormData();
for (const [k, v] of fd.entries()) {
    fd3.append(k, v);
}

console.log(fd2.get('file'));
console.log(fd3.get('file'));
