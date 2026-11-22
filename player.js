(() => {
  const stage = document.currentScript?.previousElementSibling;
  if (!stage?.matches('#av-opening-film')) return;

  const video = stage.querySelector('video');
  const skip = stage.querySelector('.av-film-skip');
  const manual = stage.querySelector('.av-film-play');
  const portrait = window.matchMedia('(max-aspect-ratio: 4/3)').matches;
  let timer;
  let complete = false;

  function finish() {
    if (complete || !stage.isConnected) return;
    complete = true;
    window.clearTimeout(timer);
    video.pause();
    video.hidden = skip.hidden = manual.hidden = true;
    stage.dataset.avState = 'finished';
  }

  function start() {
    manual.hidden = true;
    stage.dataset.avState = 'loading';
    window.clearTimeout(timer);
    timer = window.setTimeout(finish, 18000);
    video.play().catch(error => {
      if (complete) return;
      if (error.name === 'NotAllowedError') {
        stage.dataset.avState = 'manual';
        manual.hidden = false;
      } else {
        finish();
      }
    });
  }

  video.addEventListener('playing', () => {
    if (!complete) stage.dataset.avState = 'playing';
  });
  video.addEventListener('ended', finish);
  video.addEventListener('error', finish);
  skip.addEventListener('click', finish);
  manual.addEventListener('click', start);
  video.muted = true;
  video.defaultMuted = true;
  video.src = portrait ? video.dataset.tall : video.dataset.wide;
  video.removeAttribute('data-tall');
  video.removeAttribute('data-wide');
  start();
})();
