export type Mode = 'light' | 'dark';

export interface Theme {
  outerBg: string; page: string; surface: string; surfaceSunken: string;
  text: string; text2: string; border: string; link: string; linkStrong: string;
  infoBg: string; infoText: string;
}

export const LIGHT: Theme = {
  outerBg: '#ece1cf', page: '#f6efe4', surface: '#ffffff', surfaceSunken: '#f1e9d9',
  text: '#2a2a28', text2: '#4a4844', border: 'rgba(42,42,40,0.16)',
  link: '#33552b', linkStrong: '#33552b', infoBg: '#f1eef5', infoText: '#4a3f60',
};

export const DARK: Theme = {
  outerBg: '#141311', page: '#201f1c', surface: '#2c2b28', surfaceSunken: '#242320',
  text: '#f6efe4', text2: '#cbc3b6', border: 'rgba(246,239,228,0.16)',
  link: '#8bbf72', linkStrong: '#8bbf72', infoBg: '#2c283a', infoText: '#c4b8dd',
};

export const ORANGE = '#f0942f';
export const GREEN = '#4d7a3a';

export const STATUS_STYLE: Record<string, { fill: string; label: string; border: string }> = {
  pass: { fill: '#335a2b', label: 'Pass', border: '2px solid rgba(255,255,255,.28)' },
  near_limit: { fill: '#8a4d12', label: 'Near Limit', border: '2px dashed rgba(255,255,255,.6)' },
  fail: { fill: '#a8402f', label: 'Fail', border: '2px solid rgba(255,255,255,.7)' },
  not_evaluated: { fill: '#4f4d48', label: 'Not Evaluated', border: '2px dotted rgba(255,255,255,.4)' },
};

export const BANNER: Record<Mode, Record<string, { bg: string; text: string }>> = {
  light: {
    fail: { bg: '#fbe9e6', text: '#8a2f24' },
    near_limit: { bg: '#fdf0e0', text: '#7a3d0d' },
    pass: { bg: '#e9f1e3', text: '#2a4322' },
    not_evaluated: { bg: '#f1eef5', text: '#4a3f60' },
  },
  dark: {
    fail: { bg: '#3a201c', text: '#f2a99c' },
    near_limit: { bg: '#3a2a14', text: '#f0b878' },
    pass: { bg: '#223a1c', text: '#a8cf99' },
    not_evaluated: { bg: '#2c283a', text: '#c4b8dd' },
  },
};

export const BANNER_MESSAGE: Record<string, string> = {
  fail: 'This rig is over at least one legal limit — do not tow as loaded.',
  near_limit: 'Nothing is over a limit, but at least one check is close to one.',
  pass: 'Every evaluated check is within its limit.',
  not_evaluated: 'There was not enough information to evaluate this rig.',
};
