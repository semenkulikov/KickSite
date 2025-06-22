const path = require('path');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const webpack = require('webpack');

module.exports = {
  context: __dirname,
  mode: 'production',
  devtool: 'source-map',
  entry: {
    Django: './assets/Django/js/index.js',
    KickApp: './assets/KickApp/js/chat/chat.js',
    KickAppStats: './assets/KickApp/js/stats/stats.js',
  },
  output: {
    path: path.resolve(__dirname, './assets/webpack_bundles/'),
    filename: '[name].bundle.js',
    clean: true,
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: '[name].bundle.css',
    }),
    new webpack.ProvidePlugin({
      $: 'jquery',
      jQuery: 'jquery',
    }),
  ],
  optimization: {
    minimize: true,
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
