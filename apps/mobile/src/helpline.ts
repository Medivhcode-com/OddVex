/**
 * Where to get help with problem gambling. The one place these facts are written: every screen, link and
 * sentence that gives the helpline reads them from here.
 *
 * Checked on 2026-11-19 against the National Council on Problem Gambling's own pages:
 * - The National Problem Gambling Helpline is 1-800-MY-RESET (1-800-697-3738), in service since 2026-01-29.
 * - It takes calls, and texts to 800GAM (800426). It is confidential and answers 24 hours a day, every day.
 * - It is not an emergency service. In a crisis the numbers are 988 (the Suicide and Crisis Lifeline, call
 *   or text) and 911.
 * - Online chat is offered on the Council's website. The app links to the front page only, because deeper
 *   addresses move.
 * - 1-800-GAMBLER is not the national helpline (the Council on Compulsive Gambling of New Jersey runs it), so this app never gives it.
 */
export const HELPLINE = {
  name: 'National Problem Gambling Helpline',
  /** The number as the Council writes it. */
  number: '1-800-MY-RESET',
  /** The same number in digits. */
  digits: '1-800-697-3738',
  tel: 'tel:+18006973738',
  /** The text line, as letters and as the digits they stand for. */
  textTo: '800GAM',
  textDigits: '800426',
  council: 'National Council on Problem Gambling',
  site: 'https://www.ncpgambling.org',
  /** The address as shown on the link. */
  siteLabel: 'ncpgambling.org',
  crisisName: 'Suicide and Crisis Lifeline',
  crisisNumber: '988',
  crisisTel: 'tel:988',
} as const;

/** "1-800-MY-RESET (1-800-697-3738)": the number is always written both ways. */
export const HELPLINE_NUMBER = `${HELPLINE.number} (${HELPLINE.digits})`;

/** The short line shown wherever the app gives the helpline. */
export const RESPONSIBLE_GAMBLING_LINE = `21+. OddVex does not take wagers. Gambling problem? Call ${HELPLINE_NUMBER}.`;

export const HELPLINE_ABOUT = `The ${HELPLINE.name} is confidential and answers 24 hours a day, every day. Call ${HELPLINE_NUMBER} or text ${HELPLINE.textTo} (${HELPLINE.textDigits}).`;

export const HELPLINE_NOT_EMERGENCY = `The helpline is not an emergency service. In a crisis, call or text ${HELPLINE.crisisNumber} (the ${HELPLINE.crisisName}) or call 911.`;

export const HELPLINE_CHAT = `Online chat is offered on the ${HELPLINE.council}'s website.`;

/** The closing sentence of the weekly staking reminder notice. */
export const STAKE_REMINDER_HELP = `If betting is causing you stress, confidential help is available at ${HELPLINE_NUMBER}.`;
