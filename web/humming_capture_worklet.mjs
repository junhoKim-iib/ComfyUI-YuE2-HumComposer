// Capture mono PCM in blocks and leave the output silent.
const BLOCK_BYTES = 8192;

class HummingCaptureProcessor extends AudioWorkletProcessor {
    buffer = new DataView(new ArrayBuffer(BLOCK_BYTES));
    offset = 0;
    finished = false;

    constructor() {
        super();
        this.port.onmessage = () => {
            this.finished = true;
            if (this.offset) {
                const tail = this.buffer.buffer.slice(0, this.offset);
                this.port.postMessage(tail, [tail]);
            }
            this.port.postMessage('finished');
        };
    }

    process(inputs) {
        if (this.finished) return false;
        const samples = inputs[0]?.[0];
        if (!samples) return true;

        for (const sample of samples) {
            const clamped = Math.max(-1, Math.min(1, sample));
            this.buffer.setInt16(this.offset, clamped * (clamped < 0 ? 32768 : 32767), true);
            this.offset += 2;
            if (this.offset === BLOCK_BYTES) {
                const block = this.buffer.buffer;
                this.port.postMessage(block, [block]);
                this.buffer = new DataView(new ArrayBuffer(BLOCK_BYTES));
                this.offset = 0;
            }
        }
        return true;
    }
}

registerProcessor('yu-e2-humming-capture', HummingCaptureProcessor);
