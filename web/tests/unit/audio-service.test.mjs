import assert from 'node:assert/strict';
import test from 'node:test';

const { AudioService } = await import('../../src/services/AudioService.js');

test('AudioService streams supported MP3 requests with MediaSource regardless of length', () => {
    const service = new AudioService();

    assert.equal(service.shouldUseMseStream('mp3', true), true);
});

test('AudioService does not use MediaSource for unsupported or non-MP3 output', () => {
    const service = new AudioService();

    assert.equal(service.shouldUseMseStream('mp3', false), false);
    assert.equal(service.shouldUseMseStream('wav', true), false);
    assert.equal(service.shouldUseMseStream('pcm', true), false);
});

test('AudioService exposes transcript download URLs when available', () => {
    const service = new AudioService();
    service.serverTranscriptPath = 'http://localhost/download/speech_timestamps.txt';
    service.serverTranscriptJsonPath = 'http://localhost/download/speech_timestamps.json';

    assert.equal(
        service.getTranscriptDownloadUrl(),
        'http://localhost/download/speech_timestamps.txt'
    );
    assert.equal(
        service.getTranscriptJsonDownloadUrl(),
        'http://localhost/download/speech_timestamps.json'
    );
});

test('AudioService extracts download filenames for transcript preparation', () => {
    const service = new AudioService();
    service.serverDownloadPath = 'http://localhost/v1/download/speech.mp3';

    assert.equal(service.getDownloadFilename(), 'speech.mp3');
});

test('AudioService extracts download filenames from relative paths', () => {
    const service = new AudioService();
    service.serverDownloadPath = '/v1/download/speech.mp3';

    const previousWindow = global.window;
    global.window = { location: { origin: 'http://localhost' } };

    try {
        assert.equal(service.getDownloadFilename(), 'speech.mp3');
    } finally {
        global.window = previousWindow;
    }
});
