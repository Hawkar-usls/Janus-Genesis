(() => {
  'use strict';

  function textTarget(target){return target instanceof HTMLInputElement||target instanceof HTMLTextAreaElement||target?.isContentEditable;}
  addEventListener('keydown',event=>{
    if(textTarget(event.target)||event.repeat)return;
    const rt=globalThis.GENESIS_WORLD_RUNTIME_V3;
    if(!rt)return;
    if(event.code==='KeyE'){event.preventDefault();rt.leaveMark('PLAYER MARK');return;}
    if(event.code==='KeyR'){event.preventDefault();rt.returnToHearth();return;}
    if(event.code==='KeyV'){event.preventDefault();const panel=document.getElementById('mirror-panel');if(panel)panel.hidden=!panel.hidden;return;}
    if(event.code==='Digit1'){event.preventDefault();rt.setCamera('FIRST_PERSON');return;}
    if(event.code==='Digit3'){event.preventDefault();rt.setCamera('THIRD_PERSON');return;}
    if(event.code==='KeyI'){event.preventDefault();rt.setCamera('ISOMETRIC');}
  }, true);

  globalThis.GENESIS_HOTKEYS_V1=Object.freeze({
    movement:'KeyboardEvent.code: KeyW KeyA KeyS KeyD + arrows',
    actions:'KeyE mark / KeyR hearth / KeyV Mirror',
    cameras:'Digit1 first person / Digit3 third person / KeyI isometric'
  });
})();
