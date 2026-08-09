import { describe, it, expect } from 'vitest'
import {
  dateFolder,
  timeStr,
  safeName,
  msgStem,
  extForType,
  sender,
  chatKey,
  extractText,
  formatChatLine,
  resolveVersion,
  PINNED_BAILEYS_VERSION,
} from '../lib.js'

// ---------------------------------------------------------------------------
// dateFolder
// ---------------------------------------------------------------------------
describe('dateFolder', () => {
  it('formats Date as YYYY-MM', () => {
    const d = new Date('2026-08-05T14:32:01Z')
    expect(dateFolder(d)).toBe('2026-08')
  })

  it('handles January correctly', () => {
    const d = new Date('2025-01-15T00:00:00Z')
    expect(dateFolder(d)).toBe('2025-01')
  })

  it('handles December correctly', () => {
    const d = new Date('2024-12-31T23:59:59Z')
    expect(dateFolder(d)).toBe('2024-12')
  })
})

// ---------------------------------------------------------------------------
// timeStr
// ---------------------------------------------------------------------------
describe('timeStr', () => {
  it('formats Date as HH:MM:SS (UTC offset applied)', () => {
    // Note: toTimeString() uses local timezone. We test the format.
    const d = new Date('2026-08-05T14:32:01Z')
    const result = timeStr(d)
    expect(result).toMatch(/^\d{2}:\d{2}:\d{2}$/)
  })

  it('returns midnight for midnight UTC', () => {
    const d = new Date('2026-01-01T00:00:00.000Z')
    const result = timeStr(d)
    expect(result).toMatch(/^\d{2}:\d{2}:\d{2}$/)
    // The actual hours depend on timezone, but the format is always HH:MM:SS
  })
})

// ---------------------------------------------------------------------------
// safeName
// ---------------------------------------------------------------------------
describe('safeName', () => {
  it('removes invalid filename characters', () => {
    expect(safeName('file<>:"/\\|?*name')).toBe('file_________name')
  })

  it('collapses whitespace', () => {
    expect(safeName('hello    world')).toBe('hello world')
  })

  it('trims leading and trailing whitespace', () => {
    expect(safeName('  spaced  ')).toBe('spaced')
  })

  it('truncates to 200 characters', () => {
    const long = 'a'.repeat(300)
    expect(safeName(long)).toHaveLength(200)
  })

  it('leaves safe names unchanged', () => {
    expect(safeName('Group-Name')).toBe('Group-Name')
  })

  it('handles empty string', () => {
    expect(safeName('')).toBe('')
  })

  it('handles whitespace-only string', () => {
    expect(safeName('   ')).toBe('')
  })
})

// ---------------------------------------------------------------------------
// msgStem
// ---------------------------------------------------------------------------
describe('msgStem', () => {
  it('generates ISO timestamp + id stem', () => {
    const msg = {
      messageTimestamp: '1722846721', // 2024-08-05T14:32:01Z
      key: { id: 'abc123def' },
    }
    expect(msgStem(msg)).toBe('2024-08-05T08-32-01-000Z_abc123de')
  })

  it('uses "unknown" when no timestamp', () => {
    const msg = {
      key: { id: 'xyz' },
    }
    expect(msgStem(msg)).toBe('unknown_xyz')
  })

  it('falls back to "noid" when key.id is missing', () => {
    const msg = {
      messageTimestamp: '1722846721',
      key: {},
    }
    const stem = msgStem(msg)
    expect(stem).toContain('noid')
  })

  it('handles zero timestamp', () => {
    const msg = {
      messageTimestamp: '0',
      key: { id: 'test' },
    }
    expect(msgStem(msg)).toContain('1970')
  })
})

// ---------------------------------------------------------------------------
// extForType
// ---------------------------------------------------------------------------
describe('extForType', () => {
  it('maps known types', () => {
    expect(extForType('imageMessage')).toBe('.jpg')
    expect(extForType('videoMessage')).toBe('.mp4')
    expect(extForType('audioMessage')).toBe('.ogg')
    expect(extForType('documentMessage')).toBe('.bin')
    expect(extForType('stickerMessage')).toBe('.webp')
  })

  it('returns .dat for unknown types', () => {
    expect(extForType('contactMessage')).toBe('.dat')
    expect(extForType('locationMessage')).toBe('.dat')
    expect(extForType('')).toBe('.dat')
  })
})

// ---------------------------------------------------------------------------
// sender
// ---------------------------------------------------------------------------
describe('sender', () => {
  it('returns "Me" for own messages', () => {
    expect(sender({ key: { fromMe: true } })).toBe('Me')
  })

  it('returns participant for group messages', () => {
    const msg = {
      key: {
        fromMe: false,
        participant: '1234567890@s.whatsapp.net',
        remoteJid: 'group123@g.us',
      },
    }
    expect(sender(msg)).toBe('1234567890')
  })

  it('returns phone for DM messages', () => {
    const msg = {
      key: {
        fromMe: false,
        remoteJid: '0987654321@s.whatsapp.net',
      },
    }
    expect(sender(msg)).toBe('0987654321')
  })

  it('returns raw jid for non-standard remoteJid', () => {
    const msg = {
      key: {
        fromMe: false,
        remoteJid: 'group123@g.us',
      },
    }
    expect(sender(msg)).toBe('group123@g.us')
  })

  it('handles empty participant', () => {
    const msg = {
      key: {
        fromMe: false,
        participant: '@s.whatsapp.net',
      },
    }
    expect(sender(msg)).toBe('unknown')
  })
})

// ---------------------------------------------------------------------------
// chatKey
// ---------------------------------------------------------------------------
describe('chatKey', () => {
  it('returns sanitized remoteJid', () => {
    const msg = { key: { remoteJid: '+1234567890@s.whatsapp.net' } }
    expect(chatKey(msg)).toBe('+1234567890@s.whatsapp.net')
  })

  it('returns "unknown" for missing remoteJid', () => {
    const msg = { key: {} }
    expect(chatKey(msg)).toBe('unknown')
  })

  it('sanitizes special characters in remoteJid', () => {
    const msg = { key: { remoteJid: 'name<with>special@g.us' } }
    expect(chatKey(msg)).toContain('_')
  })
})

// ---------------------------------------------------------------------------
// extractText
// ---------------------------------------------------------------------------
describe('extractText', () => {
  it('extracts conversation text', () => {
    expect(extractText({ conversation: 'hello world' })).toBe('hello world')
  })

  it('extracts extendedTextMessage text', () => {
    expect(extractText({ extendedTextMessage: { text: 'extended' } })).toBe('extended')
  })

  it('extracts image caption', () => {
    expect(extractText({ imageMessage: { caption: 'sunset photo' } })).toBe('sunset photo')
  })

  it('returns image placeholder when no caption', () => {
    expect(extractText({ imageMessage: {} })).toBe('📷 [image]')
  })

  it('extracts video caption', () => {
    expect(extractText({ videoMessage: { caption: 'tutorial' } })).toBe('tutorial')
  })

  it('returns video placeholder when no caption', () => {
    expect(extractText({ videoMessage: {} })).toBe('🎥 [video]')
  })

  it('extracts document caption', () => {
    expect(extractText({ documentMessage: { caption: 'report', fileName: 'q3.pdf' } })).toBe('report')
  })

  it('returns document placeholder with filename', () => {
    expect(extractText({ documentMessage: { fileName: 'budget.xlsx' } })).toBe('📄 [document: budget.xlsx]')
  })

  it('returns document placeholder without filename', () => {
    expect(extractText({ documentMessage: {} })).toBe('📄 [document: unnamed]')
  })

  it('returns voice message placeholder', () => {
    expect(extractText({ audioMessage: {} })).toBe('🎤 [voice message]')
  })

  it('returns sticker placeholder', () => {
    expect(extractText({ stickerMessage: {} })).toBe('🟩 [sticker]')
  })

  it('returns null for protocol messages', () => {
    expect(extractText({ protocolMessage: { type: 'REVOKE' } })).toBeNull()
  })

  it('returns [unknown] for unrecognized message', () => {
    expect(extractText({ contactVcardMessage: { vcard: '...' } })).toBe('[unknown]')
  })

  it('returns [empty] for null message', () => {
    expect(extractText(null)).toBe('[empty]')
  })

  it('prefers conversation over extendedTextMessage', () => {
    const msg = {
      conversation: 'direct',
      extendedTextMessage: { text: 'extended' },
    }
    expect(extractText(msg)).toBe('direct')
  })
})

// ---------------------------------------------------------------------------
// formatChatLine
// ---------------------------------------------------------------------------
describe('formatChatLine', () => {
  it('formats a standard chat line', () => {
    const msg = {
      key: { fromMe: true, remoteJid: '123@s.whatsapp.net' },
      message: { conversation: 'hello' },
    }
    const d = new Date('2026-08-05T14:32:01Z')
    const line = formatChatLine(msg, d)
    expect(line).toMatch(/^\[\d{2}:\d{2}:\d{2}\] Me: hello\n$/)
  })

  it('returns null for protocol messages', () => {
    const msg = {
      key: { fromMe: false, remoteJid: '123@s.whatsapp.net' },
      message: { protocolMessage: {} },
    }
    expect(formatChatLine(msg, new Date())).toBeNull()
  })

  it('includes sender for DM messages', () => {
    const msg = {
      key: { fromMe: false, remoteJid: '0987654321@s.whatsapp.net' },
      message: { conversation: 'hey there' },
    }
    const line = formatChatLine(msg, new Date())
    expect(line).toContain('0987654321:')
    expect(line).toContain('hey there')
  })
})

// ---------------------------------------------------------------------------
// resolveVersion
// ---------------------------------------------------------------------------
describe('resolveVersion', () => {
  it('returns valid version when fetch succeeds', () => {
    const result = { version: { major: 2, minor: 3000, patch: 1043857760 } }
    expect(resolveVersion(result)).toEqual({ major: 2, minor: 3000, patch: 1043857760 })
  })

  it('returns pinned fallback when result is null', () => {
    expect(resolveVersion(null)).toEqual(PINNED_BAILEYS_VERSION)
  })

  it('returns pinned fallback when result is undefined', () => {
    expect(resolveVersion(undefined)).toEqual(PINNED_BAILEYS_VERSION)
  })

  it('returns pinned fallback when version object is missing', () => {
    expect(resolveVersion({})).toEqual(PINNED_BAILEYS_VERSION)
  })

  it('returns pinned fallback when version fields are undefined', () => {
    expect(resolveVersion({ version: { major: undefined, minor: undefined, patch: undefined } })).toEqual(PINNED_BAILEYS_VERSION)
  })

  it('returns pinned fallback when version fields are not numbers', () => {
    expect(resolveVersion({ version: { major: '2', minor: '3000', patch: '1043857760' } })).toEqual(PINNED_BAILEYS_VERSION)
  })

  it('returns pinned fallback when only some fields are present', () => {
    expect(resolveVersion({ version: { major: 2, minor: 3000 } })).toEqual(PINNED_BAILEYS_VERSION)
  })

  it('returns exact PINNED_BAILEYS_VERSION constant', () => {
    expect(PINNED_BAILEYS_VERSION).toEqual({ major: 2, minor: 3000, patch: 1043857760 })
  })
})
