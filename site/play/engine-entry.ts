import { Buffer } from 'buffer';
(window as any).Buffer = Buffer;

export { parse } from '../../space-rangers-quest/src/lib/qmreader';
export { QMPlayer } from '../../space-rangers-quest/src/lib/qmplayer';
export { GameState } from '../../space-rangers-quest/src/lib/qmplayer/funcs';
export { JUMP_I_AGREE } from '../../space-rangers-quest/src/lib/qmplayer/defs';
