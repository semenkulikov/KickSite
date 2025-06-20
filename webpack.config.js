const path = require('path');
const webpack = require('webpack');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');

module.exports = {
  context: __dirname,
  mode: 'production',
  devtool: false,
  plugins: [new MiniCssExtractPlugin({
    filename: '[name].bundle.css',
  })],

  entry: {
    Django: './assets/Django/js/index.js',
    KickApp: './assets/KickApp/js/chat/chat.js',
    KickAppStats: './assets/KickApp/js/stats/stats.js',
    TwitchApp: './assets/TwitchApp/js/chat/chat.js',
    TwitchAppStats: './assets/TwitchApp/js/stats/stats.js',
  },
  output: {
    path: path.resolve(__dirname, './assets/webpack_bundles/'),
    filename: '[name].bundle.js',
    clean: true,
  },
  module: {
    rules: [
      {
        test: /\.css$/i,
        use: [MiniCssExtractPlugin.loader, 'css-loader'],
      },
    ],
  },
};
