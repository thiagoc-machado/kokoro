import assert from 'node:assert/strict';
import test from 'node:test';

class FakeClassList {
    constructor() {
        this.classes = new Set();
    }

    add(...names) {
        names.forEach((name) => this.classes.add(name));
    }

    remove(...names) {
        names.forEach((name) => this.classes.delete(name));
    }

    toggle(name, force) {
        if (force === undefined ? !this.classes.has(name) : force) {
            this.classes.add(name);
        } else {
            this.classes.delete(name);
        }
    }

    contains(name) {
        return this.classes.has(name);
    }
}

function setupDocument() {
    const transcriptButton = {
        classList: new FakeClassList(),
        style: {},
        disabled: false,
    };

    global.document = {
        getElementById(id) {
            if (id === 'transcript-download-btn') {
                return transcriptButton;
            }
            return { addEventListener() {} };
        },
        querySelector() {
            return { addEventListener() {} };
        },
        addEventListener() {},
    };

    global.window = {
        addEventListener() {},
    };

    return transcriptButton;
}

test('App transcript button transitions between hidden, creating, and ready states', async () => {
    const transcriptButton = setupDocument();
    const { App } = await import('../../src/App.js');

    const app = Object.create(App.prototype);
    app.elements = { transcriptDownloadBtn: transcriptButton };

    app.setTranscriptButtonState('hidden');
    assert.equal(transcriptButton.style.display, 'none');
    assert.equal(transcriptButton.disabled, false);
    assert.equal(transcriptButton.classList.contains('creating'), false);
    assert.equal(transcriptButton.classList.contains('ready'), false);

    app.setTranscriptButtonState('creating');
    assert.equal(transcriptButton.style.display, '');
    assert.equal(transcriptButton.disabled, true);
    assert.equal(transcriptButton.classList.contains('creating'), true);
    assert.equal(transcriptButton.classList.contains('ready'), false);

    app.setTranscriptButtonState('ready');
    assert.equal(transcriptButton.style.display, '');
    assert.equal(transcriptButton.disabled, false);
    assert.equal(transcriptButton.classList.contains('creating'), false);
    assert.equal(transcriptButton.classList.contains('ready'), true);
});
