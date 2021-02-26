const path = require('path');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const CssMinimizerPlugin = require('css-minimizer-webpack-plugin');
const CopyPlugin = require('copy-webpack-plugin');
const { WebpackManifestPlugin } = require('webpack-manifest-plugin');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');
const ImageMinimizerPlugin = require('image-minimizer-webpack-plugin');

module.exports = (env, options) => {
	let config = {
		entry: {
			main: "./main.js",
			login: "./login.js",
			signup: "./signup.js"
		},
		output: {
			path: path.resolve(__dirname, './fenetre/static'),
			filename: options.mode == 'development' ? '[name].js' : '[name].[contenthash].js',
			publicPath: ""
		},
		context: path.resolve(__dirname, './websrc'),
		module: {
			rules: [
				{
					test: /\.(sa|sc|c)ss$/,
					use: [
						MiniCssExtractPlugin.loader,
						'css-loader',
						'sass-loader'
					]
				},
				{
					test: /\.m?js$/,
					exclude: /node_modules/,
					use: {
						loader: 'babel-loader'
					}
				},
				{
					test: /\.svg$/,
					loader: 'file-loader',
					options: {
						name: options.mode == 'development' ? '[path][name].[ext]' : '[name].[contenthash].[ext]',
						publicPath: "/static"
					}
				}
			]
		},
		plugins: [
			new CleanWebpackPlugin({
				cleanOnceBeforeBuildPatterns: ['**/*', '!.keep'],
				cleanStaleWebpackAssets: false
			}),
			new MiniCssExtractPlugin({
				filename: options.mode == 'development' ? '[name].css' : '[name].[contenthash].css'
			}),
			new CopyPlugin({
				patterns: [
					{ from: './favicon.ico', to: options.mode == 'development' ? './favicon.ico' : './favicon.[contenthash].ico' },
				]
			}),
			new WebpackManifestPlugin()
		],
		devtool: options.mode == 'development' ? 'eval-source-map' : false,
		optimization: {
			splitChunks: {
				cacheGroups: {
					commons: {
						test: /[\\/]node_modules[\\/]/,
						name: 'vendors',
						chunks: 'all'
					}
				}
			},
			minimize: options.mode == 'production',
			minimizer: [
				new TerserPlugin(),
				new CssMinimizerPlugin(),
				new ImageMinimizerPlugin({
					minimizerOptions: {
						plugins: [
							['svgo', {plugins: [{removeViewBox: false}]}]
						]
					}
				})
			]
		}
	};
	return config;
}
