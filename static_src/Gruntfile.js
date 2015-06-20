'use strict';

module.exports = function (grunt) {
    grunt.initConfig({
        pkg: grunt.file.readJSON('package.json'),

        sass: {
            options: {
                sourceMap: true,
                fontPath: '../static/fonts',
                imagePath: '../static/images',
                includePaths: [
                    '/Library/Ruby/Gems/2.0.0/gems/compass-0.12.7/frameworks/compass/stylesheets',
                    '/Library/Ruby/Gems/2.0.0/gems/bootstrap-sass-3.3.0.1/assets/stylesheets/',
                ]

            },
            compile: {
                files: {
                    '../static/css/styles.css': 'scss/styles.scss',
                    '../static/css/admin.css': 'scss/admin.scss',
                }
            }
        },

        libsass_image: {
            gen: {
                files: [{
                    cwd: "../static",
                    src: [
                        "images/**/*.{png,jpg,gif,jpeg}",
                    ],
                    dest: "scss/_imagemap.scss"
                }],
            }
        },

        handlebars: {
            options: {
                namespace: 'Shoffle.Template',
                processName: function (filePath) {
                    var arr = filePath.split('/');
                    var filename = arr[arr.length - 1];
                    filename = filename.substr(0, filename.length - 4);
                    return filename.toUpperCase();
                }
            },
            'js/hbs/templates.js': ['js/hbs/*.hbs']
        },


        uglify: {
            '../static/js/scripts.min.js': ['js/vendor/jquery*.js', 'js/vendor/bootstrap.js', 'js/plugins/*.js', 'js/hbs/templates.js', 'js/scripts.js'],
            options: {
                //beautify: true
                compress: true
            }
        },

        clean: ['js/hbs/templates.js'],

        watch: {

            options: {
                livereload: true,
                spawn: false,
                reload: false
            },
            scripts: {
                files: ['js/**/*.*'],
                tasks: ['handlebars', 'uglify', 'clean']
            },

            templates: {
                files: ['../templates/**/*.html']
            },

            sass: {
                files: ['scss/**/*.*'],
                tasks: ['sass']
            },

            images: {
                files: ['../static/images/**/*.*'],
                tasks: ['libsass_image']
            },
        }
    });

    // These plugins provide necessary tasks.

    grunt.loadNpmTasks('grunt-contrib-handlebars');
    grunt.loadNpmTasks('grunt-contrib-concat');
    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.loadNpmTasks('grunt-contrib-clean');
    grunt.loadNpmTasks('grunt-libsass-image');
    grunt.loadNpmTasks('grunt-sass');

    // Default task.
    grunt.registerTask('default', ['handlebars', 'uglify', 'clean', 'libsass_image', 'sass', 'watch']);

};