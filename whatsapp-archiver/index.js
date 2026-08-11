/**
 * WhatsApp Archiver — Baileys-based message and media export
 *
 * Connects as a WhatsApp Web multi-device client, then continuously
 * exports incoming messages to plain-text files and downloads all
 * attachments (photos, audio, video, documents) to dated folders.
 *
 * Output layout:
 *   /config/sessions/{account}/  — Baileys auth state (persistent)
 *   /data/chats/{account}/       — appended .txt per conversation
 *   /data/media/{account}/       — downloaded attachments by type
 *
 * Environment:
 *   SESSION_DIR — Baileys session storage (default: /config/sessions)
 *   DATA_DIR    — exports root (chats, media) (default: /data)
 *   ACCOUNT_NAME — label for this session (default: default)
 */

import {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  getContentType,
  downloadMediaMessage,
} from '@whiskeysockets/baileys'
import fs from 'fs/promises'
import path from 'path'
import {
  dateFolder,
  safeName,
  msgStem,
  extForType,
  sender,
  chatKey,
  extractText,
  formatChatLine,
  resolveVersion,
  PINNED_BAILEYS_VERSION,
  renderQR,
} from './lib.js'

// ---------------------------------------------------------------------------
// Reconnect state (module-scoped, not global)
// ---------------------------------------------------------------------------
let reconnectAttempts = 0
const MAX_RETRY_DELAY = 300000  // 5 min cap

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const CONFIG_DIR = process.env.CONFIG_DIR || '/config'
const DATA_DIR = process.env.DATA_DIR || '/data'
const ACCOUNT_NAME = process.env.ACCOUNT_NAME || 'default'
const SESSION_DIR = path.join(CONFIG_DIR, 'sessions', ACCOUNT_NAME)
const CHATS_DIR = path.join(DATA_DIR, 'chats', ACCOUNT_NAME)
const MEDIA_DIR = path.join(DATA_DIR, 'media', ACCOUNT_NAME)

// ---------------------------------------------------------------------------
// FS helpers
// ---------------------------------------------------------------------------

/** Ensure a directory exists (recursive mkdir). */
async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true })
}

// ---------------------------------------------------------------------------
// Media download
// ---------------------------------------------------------------------------
async function downloadMedia(msg, sock) {
  const type = getContentType(msg)
  if (!type || !['imageMessage', 'videoMessage', 'audioMessage', 'documentMessage', 'stickerMessage'].includes(type)) {
    return null
  }

  try {
    const stream = await downloadMediaMessage(
      msg,
      'stream',
      {},
      {
        logger: console,
        reuploadRequest: sock.updateMediaMessage,
      }
    )

    if (!stream) return null

    const mediaType = type.replace('Message', '').toLowerCase()
    const folder = path.join(MEDIA_DIR, mediaType, dateFolder(new Date()))
    await ensureDir(folder)

    const filename = msgStem(msg) + extForType(type)
    const filePath = path.join(folder, filename)

    return new Promise((resolve, reject) => {
      const writeStream = fs.createWriteStream(filePath)
      stream.pipe(writeStream)
      writeStream.on('finish', () => resolve(filePath))
      writeStream.on('error', reject)
    })
  } catch (err) {
    console.error(`[media] failed to download ${type}:`, err.message)
    return null
  }
}

// ---------------------------------------------------------------------------
// Chat text append
// ---------------------------------------------------------------------------
async function appendChat(msg) {
  const chat = chatKey(msg)
  const chatFile = path.join(CHATS_DIR, safeName(chat) + '.txt')
  await ensureDir(CHATS_DIR)

  const d = msg.messageTimestamp
    ? new Date(Number(msg.messageTimestamp) * 1000)
    : new Date()

  const line = formatChatLine(msg, d)
  if (line === null) return // protocol messages — skip

  await fs.appendFile(chatFile, line, 'utf-8')
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
  console.log(`[archiver] account: ${ACCOUNT_NAME}`)
  console.log(`[archiver] config dir: ${CONFIG_DIR}`)
  console.log(`[archiver] data dir: ${DATA_DIR}`)

  // Ensure dirs exist
  await ensureDir(SESSION_DIR)
  await ensureDir(CHATS_DIR)
  await ensureDir(MEDIA_DIR)

  // Check version (suppresses WA warning)
  let version
  try {
    const result = await fetchLatestBaileysVersion()
    version = resolveVersion(result)
    console.log(`[archiver] baileys v${version[0]}.${version[1]}.${version[2]}`)
  } catch (err) {
    version = PINNED_BAILEYS_VERSION
    console.warn(
      `[archiver] failed to fetch latest Baileys version: ${err.message}. Using pinned fallback v${version[0]}.${version[1]}.${version[2]}`
    )
  }

  // Persistent auth state
  const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR)

  const sock = makeWASocket({
    version,
    auth: state,
    // Emulate desktop for more message history
    browser: ['WhatsApp Archiver', 'Chrome', '1.0'],
    // Sync full history on first connect (v6.7.24+ uses shouldSyncHistoryMessage instead of syncFullHistory)
    shouldSyncHistoryMessage: () => true,
    // Don't mark online immediately
    markOnlineOnConnect: false,
    // Enable app state MAC verification to fix "tried remove, but no previous op" error
    appStateMacVerification: {
      patch: true,
      snapshot: true,
    },
  })

  // Save credentials (session persistence)
  sock.ev.on('creds.update', saveCreds)

  // Connection state
  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update

    if (qr) {
      await renderQR(qr)
      console.log('[archiver] Scan the QR above with WhatsApp > Linked Devices (refreshes every ~20s)')
    }

    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut
      console.log(
        `[archiver] connection closed: ${statusCode === 402 ? 'logged out' : statusCode || 'unknown'}, ` +
        `reconnecting: ${shouldReconnect}`
      )
      if (shouldReconnect) {
        const baseDelay = Math.min(5000 * Math.pow(2, reconnectAttempts), MAX_RETRY_DELAY)
        const jitter = Math.random() * 1000
        reconnectAttempts++
        console.log(`[archiver] reconnecting in ${Math.round((baseDelay + jitter) / 1000)}s (attempt ${reconnectAttempts})...`)
        setTimeout(main, baseDelay + jitter)
      } else {
        console.log('[archiver] logged out. Clear session dir and re-scan to restart.')
        process.exit(1)
      }
    } else if (connection === 'open') {
      reconnectAttempts = 0
      console.log('[archiver] connected and listening for messages...')
    }
  })

  // Process incoming messages
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    // Only process new messages (not sync or notify)
    if (type !== 'notify') return

    for (const msg of messages) {
      if (!msg.message || !msg.messageTimestamp) continue

      try {
        // Append text to chat file
        await appendChat(msg)

        // Download media in background
        downloadMedia(msg, sock).then((filePath) => {
          if (filePath) {
            console.log(`[media] saved: ${path.relative(MEDIA_DIR, filePath)}`)
          }
        }).catch((err) => {
          console.error(`[media] background download error:`, err.message)
        })
      } catch (err) {
        console.error(`[archiver] error processing message:`, err.message)
      }
    }
  })

  console.log('[archiver] waiting for connection...')
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
main().catch((err) => {
  console.error('[archiver] fatal:', err)
  process.exit(1)
})
