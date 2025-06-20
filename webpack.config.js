const path = require('path');
const webpack = require('webpack');

module.exports = {
  context: __dirname,
  mode: 'production',
  devtool: false,

  entry: {
    Django: {
      import: "./assets/Django/js/index",
      filename: "[name]/static/[name]/js/[name].bundle.js"
    },
    TwitchAppChat: {
      import: "./assets/TwitchApp/js/chat/chat",
      filename: "TwitchApp/static/TwitchApp/js/[name].bundle.js"
    },
    TwitchAppStats: {
      import: "./assets/TwitchApp/js/stats/stats",
      filename: "TwitchApp/static/TwitchApp/js/[name].bundle.js"
    },
    KickAppChat: {
      import: "./assets/KickApp/js/chat/chat",
      filename: "KickApp/static/KickApp/js/[name].bundle.js"
    },
    KickAppStats: {
      import: "./assets/KickApp/js/stats/stats",
      filename: "KickApp/static/KickApp/js/[name].bundle.js"
    },
  },
  output: {
    path: path.join(__dirname, "/"),
  },
};
