const path = require('path');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const BrowserSyncPlugin = require('browser-sync-webpack-plugin');
const autoprefixer = require('autoprefixer');

module.exports = {
    entry: {
        style: './assets/scss/style.scss',
        responsive: './assets/scss/responsive.scss'
    },
    output: {
        path: path.resolve(__dirname, 'assets/css'),
    },
    module: {
        rules: [
            {
                test: /\.scss$/,
                use: [
                    MiniCssExtractPlugin.loader,
                    'css-loader',
                    {
                        loader: 'postcss-loader',
                        options: {
                            postcssOptions: {
                                plugins: [
                                    autoprefixer(),
                                ],
                            },
                        },
                    },
                    {
                        loader: 'sass-loader',
                        options: {
                            implementation: require('sass'), // Use Dart Sass explicitly to avoid deprecation
                            sassOptions: {},
                        },
                    },
                ],
            },
        ],
    },
    plugins: [
        new MiniCssExtractPlugin({
            filename: '[name].css',
        }),
        new BrowserSyncPlugin({
            host: 'localhost',
            port: 3000,
            server: { baseDir: ['./'] },
            startPath: 'template/index.html',
            files: ['./assets/css/*.css', './template/*.html'],
        }),
    ],
};