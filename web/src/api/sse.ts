export interface SSEEvent { event: string; data: string }

/** Incrementally parse an SSE byte stream into events. Multi-line data joined with \n. */
export async function* parseSSE(stream: ReadableStream<Uint8Array>): AsyncGenerator<SSEEvent> {
  const reader = stream.getReader();
  const dec = new TextDecoder();
  let buf = "";
  const parseBlock = (block: string): SSEEvent | null => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith(":") || line === "") continue;
      const i = line.indexOf(":");
      const field = i === -1 ? line : line.slice(0, i);
      let val = i === -1 ? "" : line.slice(i + 1);
      if (val.startsWith(" ")) val = val.slice(1);
      if (field === "event") event = val;
      else if (field === "data") data.push(val);
    }
    return data.length ? { event, data: data.join("\n") } : null;
  };
  try {
    for (;;) {
      const { value, done } = await reader.read();
      buf += dec.decode(value, { stream: !done });
      buf = buf.replace(/\r\n/g, "\n");
      if (!done && buf.endsWith("\r")) { /* wait: next chunk may start with \n */ }
      else buf = buf.replace(/\r/g, "\n");
      let idx: number;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const ev = parseBlock(buf.slice(0, idx));
        buf = buf.slice(idx + 2);
        if (ev) { if (ev.data === "[DONE]") return; yield ev; }
      }
      if (done) break;
    }
    const last = parseBlock(buf);
    if (last && last.data !== "[DONE]") yield last;
  } finally {
    await reader.cancel().catch(() => undefined); // early exit: don't leave the connection open
    reader.releaseLock();
  }
}
