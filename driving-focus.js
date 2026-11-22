/* Window focus is not the same as tab visibility: Streamlit embeds this view.
 * Clicking a surrounding page must clear held keys without opening a dialog. */
export class DrivingFocusPolicy {
 constructor(){this.hidden=false;this.resumeOnVisible=false;}
 blur(){return 'clear-input';}
 cancelAutoResume(){this.resumeOnVisible=false;}
 visibility(hidden,running){
  if(hidden){if(!this.hidden)this.resumeOnVisible=running;this.hidden=true;return running?'suspend':null;}
  const resume=this.hidden&&this.resumeOnVisible;this.hidden=false;this.resumeOnVisible=false;return resume?'resume':null;
 }
}
