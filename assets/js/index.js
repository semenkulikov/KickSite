// Import JQuery
import jquery from 'jquery';
window.$ = jquery;
window.jQuery = jquery;

// Import Bootstrap SCSS instead of CSS
import 'bootstrap/scss/bootstrap.scss';
// import 'bootstrap/dist/js/bootstrap.bundle.js';
import * as bootstrap from 'bootstrap';
window.bootstrap = bootstrap;

// Import project styles
import '../css/login.css';
import '../css/chat.css';
import '../css/stat.css';
import '../css/channel-modal.css';

// Import project scripts
import '../KickApp/js/chat/on-load.js';
import '../KickApp/js/chat/kick-ws.js';
import '../KickApp/js/chat/kick-send.js';
import '../KickApp/js/chat/kick-account.js';
import '../KickApp/js/chat/kick-range-slider.js';
import '../KickApp/js/chat/kick-auto-messages.js';
import '../KickApp/js/chat/kick-work.js';
import '../KickApp/js/stats/stats.js';
import '../Django/js/footer.js';

// Specific imports for chat functionality
import { changeChannel, changeViewChannel } from '../KickApp/js/chat/kick-channel.js';
import { getKickChannel } from '../KickApp/js/chat/kick-channel-db.js';
import { showAlert } from '../KickApp/js/chat/alert.js';


// --- Event Listeners ---

// Handle channel change
$('#changeChannel').on('click', function() {
  changeChannel();
});

// --- Initial page load logic ---

// Get and set the initial channel
getKickChannel().then(channel => {
  if (channel && channel.channel) {
    changeViewChannel(true, channel.channel);
  } else {
    changeViewChannel(false);
  }
}).catch(error => {
  console.error("Error getting kick channel:", error);
  showAlert("Could not load channel settings.", "alert-danger");
  changeViewChannel(false);
});

document.addEventListener('DOMContentLoaded', function() {
  if (window.bootstrap) {
    document.querySelectorAll('.dropdown-toggle').forEach(el => {
      new bootstrap.Dropdown(el);
    });
  }
  // Глобальный фикс для backdrop/modal-open
  document.querySelectorAll('.modal').forEach(function(modalEl) {
    modalEl.addEventListener('hidden.bs.modal', function() {
      document.body.classList.remove('modal-open');
      document.body.style = '';
      document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
    });
  });
}); 