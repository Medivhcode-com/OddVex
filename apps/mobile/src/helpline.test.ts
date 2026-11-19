import { HELPLINE, HELPLINE_ABOUT, HELPLINE_CHAT, HELPLINE_NOT_EMERGENCY, HELPLINE_NUMBER, RESPONSIBLE_GAMBLING_LINE, STAKE_REMINDER_HELP } from '@/helpline';
import { BANNED_COPY } from '@/test/banned-copy';

// The source files are read from disk. This package has no Node type definitions, so the functions used are
// described here rather than adding a dependency for one test (as in components/community-copy.test.ts).
type Fs = { readdirSync(path: string): string[]; readFileSync(path: string, encoding: 'utf8'): string; statSync(path: string): { isDirectory(): boolean } };
const { readdirSync, readFileSync, statSync } = jest.requireActual<Fs>('fs');
const { join, relative } = jest.requireActual<{ join(...parts: string[]): string; relative(from: string, to: string): string }>('path');
declare const __dirname: string;

const KEYPAD: Record<string, string> = { ABC: '2', DEF: '3', GHI: '4', JKL: '5', MNO: '6', PQRS: '7', TUV: '8', WXYZ: '9' };
const dial = (text: string) =>
  text
    .toUpperCase()
    .replace(/[A-Z]/g, (letter) => Object.entries(KEYPAD).find(([letters]) => letters.includes(letter))?.[1] ?? letter)
    .replace(/\D/g, '');

const SRC = join(__dirname);
function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

describe('helpline facts', () => {
  it('spells the same number three ways', () => {
    expect(HELPLINE.number).toBe('1-800-MY-RESET');
    expect(HELPLINE.digits).toBe('1-800-697-3738');
    expect(dial(HELPLINE.number)).toBe(dial(HELPLINE.digits));
    expect(HELPLINE.tel).toBe('tel:+18006973738');
    expect(HELPLINE.tel).toBe(`tel:+${dial(HELPLINE.digits)}`);
    expect(HELPLINE_NUMBER).toBe('1-800-MY-RESET (1-800-697-3738)');
  });

  it('gives the text line in letters and in digits', () => {
    expect(HELPLINE.textTo).toBe('800GAM');
    expect(HELPLINE.textDigits).toBe('800426');
    expect(dial(HELPLINE.textTo)).toBe(HELPLINE.textDigits);
  });

  it('links to the front page of the Council, not to a deeper address', () => {
    expect(HELPLINE.site).toBe('https://www.ncpgambling.org');
    expect(HELPLINE.site).toBe(`https://www.${HELPLINE.siteLabel}`);
  });

  it('words the short line as agreed', () => {
    expect(RESPONSIBLE_GAMBLING_LINE).toBe('21+. OddVex does not take wagers. Gambling problem? Call 1-800-MY-RESET (1-800-697-3738).');
  });

  it('says what the helpline is, and that it is not an emergency service', () => {
    expect(HELPLINE_ABOUT).toBe(
      'The National Problem Gambling Helpline is confidential and answers 24 hours a day, every day. Call 1-800-MY-RESET (1-800-697-3738) or text 800GAM (800426).',
    );
    expect(HELPLINE_NOT_EMERGENCY).toBe(
      'The helpline is not an emergency service. In a crisis, call or text 988 (the Suicide and Crisis Lifeline) or call 911.',
    );
    expect(HELPLINE_CHAT).toBe("Online chat is offered on the National Council on Problem Gambling's website.");
    expect(STAKE_REMINDER_HELP).toBe('If betting is causing you stress, confidential help is available at 1-800-MY-RESET (1-800-697-3738).');
  });

  it('uses no banned phrase', () => {
    for (const text of [RESPONSIBLE_GAMBLING_LINE, HELPLINE_ABOUT, HELPLINE_NOT_EMERGENCY, HELPLINE_CHAT, STAKE_REMINDER_HELP]) {
      for (const banned of BANNED_COPY) expect(text).not.toMatch(banned);
    }
  });
});

describe('the helpline in the rest of the app', () => {
  const files = sources(SRC).filter((path) => !/\.test\.tsx?$/.test(path));
  const others = files.filter((path) => relative(SRC, path) !== 'helpline.ts');

  it('is written in one module only', () => {
    expect(files.length).toBeGreaterThan(100);
    for (const path of others) {
      const text = readFileSync(path, 'utf8');
      const found = /MY-RESET|697-?3738|8006973738|800GAM|800426|ncpgambling/i.test(text);
      expect({ path: relative(SRC, path), found }).toEqual({ path: relative(SRC, path), found: false });
    }
  });

  it('names the New Jersey line only to say that it is not the national helpline', () => {
    // The old number, as a word and in digits. Written in halves so a search of the source for the word finds
    // only the one sentence that explains it.
    const old = new RegExp(`${'GAMB'}${'LER'}|426-?2537`, 'i');
    let explained = 0;
    for (const path of sources(SRC)) {
      for (const line of readFileSync(path, 'utf8').split('\n')) {
        if (!old.test(line)) continue;
        expect({ path: relative(SRC, path), line, explains: /^\s*(\*|\/\/).*New Jersey/.test(line) }).toEqual({ path: relative(SRC, path), line, explains: true });
        explained += 1;
      }
    }
    expect(explained).toBeLessThanOrEqual(1);
  });
});
