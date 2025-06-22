// Import JQuery
import jquery from 'jquery';
window.$ = jquery;
window.jQuery = jquery;

// Import Bootstrap
import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap/dist/js/bootstrap.bundle.min.js';

// Import project styles
import '../css/login.css';
import '../css/chat.css';
import '../css/stat.css';
import '../css/channel-modal.css';

// Import project scripts from KickApp
import '../KickApp/js/chat/on-load';
import '../KickApp/js/chat/kick-ws';
import '../KickApp/js/chat/kick-send';
import '../KickApp/js/chat/kick-channel';
import '../KickApp/js/chat/kick-account';
import '../KickApp/js/chat/kick-range-slider';
import '../KickApp/js/chat/kick-auto-messages';
import '../KickApp/js/chat/kick-work';

// Import stats scripts
import '../KickApp/js/stats/stats.js';

// Import other general scripts
import '../Django/js/footer'; 