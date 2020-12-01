const path = require('path');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const CssMinimizerPlugin = require('css-minimizer-webpack-plugin');

module.exports = (env, options) => {
	return {
		entry: {
			main: "./websrc/main.js"
		},
		output: {
			path: path.resolve(__dirname, './fenetre/static'),
			filename: '[name].js'
		},
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
				}
			]
		},
		plugins: [
			new MiniCssExtractPlugin()
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
				new CssMinimizerPlugin()
			]
		}
	};
}
