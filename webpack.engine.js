const path = require('path');
const webpack = require('webpack');

module.exports = {
  mode: 'production',
  entry: './site/play/engine-entry.ts',
  output: {
    path: path.resolve(__dirname, 'site/play'),
    filename: 'qmengine.js',
    library: 'QMEngine',
    libraryTarget: 'window',
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.js'],
    fallback: {
      buffer: require.resolve('buffer/'),
      assert: false,
    },
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: [
          {
            loader: 'ts-loader',
            options: {
              transpileOnly: true,
              compilerOptions: {
                target: 'es5',
                module: 'commonjs',
                lib: ['es6', 'dom'],
                jsx: 'react',
                esModuleInterop: true,
                experimentalDecorators: true,
                emitDecoratorMetadata: true,
                inlineSourceMap: true,
              },
            },
          },
        ],
      },
    ],
  },
  plugins: [
    new webpack.ProvidePlugin({
      Buffer: ['buffer', 'Buffer'],
    }),
  ],
};
