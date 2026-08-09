/**
 * WhatsApp Archiver — Pure utility functions
 *
 * Extracted from index.js so they can be unit-tested without Baileys or FS.
 */

// ---------------------------------------------------------------------------
// Version resolution
// ---------------------------------------------------------------------------

/** Pinned fallback version (Baileys build profile format).
 *  Matches the pattern used by @whiskeysockets/baileys ^6.7.7.
 *  Baileys expects version as an array [major, minor, patch] for .join() calls.
 */
export const PINNED_BAILEYS_VERSION = [2, 3000, 1043857760]

/**
 * Resolve the Baileys version from fetchLatestBaileysVersion result.
 * Returns the pinned fallback when input is null/undefined/missing fields.
 * @param {object|null|undefined} result - Result from fetchLatestBaileysVersion
 * @returns {array} Valid version array [major, minor, patch]
 */
export function resolveVersion(result) {
  if (!result?.version) {
    return PINNED_BAILEYS_VERSION
  }
  const { major, minor, patch } = result.version
  if (typeof major !== 'number' || typeof minor !== 'number' || typeof patch !== 'number') {
    return PINNED_BAILEYS_VERSION
  }
  return [major, minor, patch]
}

// ---------------------------------------------------------------------------
// Date / Time formatting
// ---------------------------------------------------------------------------

/** Format a Date as YYYY-MM for folder naming. */
export function dateFolder(d) {
  return d.toISOString().slice(0, 7) // "2026-08"
}

/** Format a Date as HH:MM:SS for chat log lines. */
export function timeStr(d) {
  return d.toTimeString().slice(0, 8) // "14:32:01"
}

// ---------------------------------------------------------------------------
// Filename helpers
// ---------------------------------------------------------------------------

/** Sanitize a chat name into a safe filename. */
export function safeName(raw) {
  return raw
    .replace(/[<>:"/\\|?*]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 200)
}

/** Derive a filename stem from a message key. */
export function msgStem(msg) {
  const ts = msg.messageTimestamp
    ? new Date(Number(msg.messageTimestamp) * 1000).toISOString().replace(/[:.]/g, '-')
    : 'unknown'
  return `${ts}_${String(msg.key.id || 'noid').slice(0, 8)}`
}

/** Map Baileys content type to a file extension. */
export function extForType(type) {
  const map = {
    imageMessage: '.jpg',
    videoMessage: '.mp4',
    audioMessage: '.ogg',
    documentMessage: '.bin',
    stickerMessage: '.webp',
  }
  return map[type] || '.dat'
}

// ---------------------------------------------------------------------------
// Message metadata
// ---------------------------------------------------------------------------

/** Get the sender display name for a message. */
export function sender(msg) {
  if (msg.key.fromMe) return 'Me'
  // Group: participant
  if (msg.key.participant) {
    const jid = msg.key.participant
    return jid.split('@')[0] || 'unknown'
  }
  // DM: remoteJid
  const jid = msg.key.remoteJid
  if (jid.endsWith('@s.whatsapp.net')) return jid.replace('@s.whatsapp.net', '')
  return jid
}

/** Get the chat key (filename-safe conversation identifier). */
export function chatKey(msg) {
  const remote = msg.key.remoteJid || 'unknown'
  return safeName(remote)
}

// ---------------------------------------------------------------------------
// Message text extraction
// ---------------------------------------------------------------------------

/** Extract displayable text from a Baileys message object. */
export function extractText(messageObj) {
  if (!messageObj) return '[empty]'
  if ('conversation' in messageObj) return messageObj.conversation
  if (messageObj.extendedTextMessage?.text) return messageObj.extendedTextMessage.text
  if (messageObj.imageMessage?.caption) return messageObj.imageMessage.caption
  if (messageObj.videoMessage?.caption) return messageObj.videoMessage.caption
  if (messageObj.documentMessage?.caption) return messageObj.documentMessage.caption
  if (messageObj.audioMessage) return '🎤 [voice message]'
  if (messageObj.imageMessage) return '📷 [image]'
  if (messageObj.videoMessage) return '🎥 [video]'
  if (messageObj.documentMessage)
    return `📄 [document: ${messageObj.documentMessage.fileName || 'unnamed'}]`
  if (messageObj.stickerMessage) return '🟩 [sticker]'
  if (messageObj.protocolMessage) return null // edits, deletes — skip
  return '[unknown]'
}

/** Format a chat log line: `[HH:MM:SS] Sender: text` */
export function formatChatLine(msg, d) {
  const s = sender(msg)
  const text = extractText(msg.message)
  if (text === null) return null // protocol messages
  return `[${timeStr(d)}] ${s}: ${text}\n`
}
