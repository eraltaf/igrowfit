$(function () {
    $('.result .holder').masonry({
        gutter: '.gutter-sizer',
        itemSelector: '.schedule,.category'
    });

    $('.participating-studios .holder').masonry({
        gutter: 10,
        itemSelector: '.participating-studio'
    });

    if ($('#date').length > 0) {
        var start_date = new Date(new Date().getTime() + 24 * 60 * 60 * 1000);
        var end_date = new Date(new Date().getTime() + 31 * 24 * 60 * 60 * 1000);

        $('#date').datepicker({
            viewMode: 'days', format: 'dd-mm-yyyy',
            onRender: function (date) {
                return date.valueOf() < start_date.valueOf() | date.valueOf() > end_date.valueOf() ? 'disabled' : '';
            },
        }).on('show', function (evt) {
            if ($('#date').width() > $('.datepicker').width()) {
                $('.datepicker').css('left', $('#date').offset().left + ($('#date').width() - $('.datepicker').width()) / 2);
            }

        });
    }
    $('#tablesorter').tablesorter();
    $('[placeholder]').focus(function () {
        var input = $(this);
        if (!input.val()) {
            input.attr('placeholder', '');
            //input.removeClass('placeholder');
        }
    }).blur(function () {
        var input = $(this);
        if (!input.attr('ph')) {
            input.attr('ph', input.attr('placeholder'))
        }
        if (input.val() == '') {
            input.attr('placeholder', input.attr('ph'));
        }
    }).blur();
});

$(window).load(function () {
    $(window).trigger('resize');
});

function login() {
    if ($(window).width() < 1024) {
        document.location.href = '/login';
    }
}

function show_nav() {
    $('ul.nav').show();
}

function book(id) {
    if (!is_loggedin) {
        alert('Please login first.');
        return;
    }
    if (confirm('Are you sure you want to book this class?')) {
        $.get('/book/' + id, function (data) {
            data = $.parseJSON(data);
            alert(data.message);
            if (data.result == 'Success') {
                document.location.href = '/dashboard';
            }
        });
    }
}

function cancel(id) {
    if (confirm('Are you sure to cancel this class?')) {
        $.get('/cancel/' + id, function (data) {
            document.location.href = '/dashboard';
        });
    }
}


function selectTime(div) {
    var v = $(div).html();
    if (v == 'ANY TIME') {
        $('#timeDropdown').addClass('empty');
        $('input#time').val('');
    } else {
        $('#timeDropdown').removeClass('empty');
        $('input#time').val(v);
    }

    $('#timeDropdown').html(v);
}

function validate_search() {
    if (!($('#keyword').val() || $('#date').val() || $('#time').val())) {
        alert('Please specify a search criteria.');
        return false;
    }
}

function toggle_details(ele) {
    var details = $($(ele).parent().find('.details'));
    if (details.hasClass('hidden')) {
        details.removeClass('hidden');
        $(ele).html('LESS');
    } else {
        details.addClass('hidden');
        $(ele).html('MORE');
    }

    $('.result .holder').data('masonry').layout();
}

function slideTo(div) {
    if ($(div).length == 0) {
        document.location.href = '/';
        return;
    }
    $('html,body').animate({scrollTop: $(div).offset().top}, 500);
}

function attend(div, id, name) {
    if (!confirm('Are you sure ' + name + ' attended the class?')) {
        return;
    }
    $.get('/attend/' + id, function (data) {
        if (data != 'Success') {
            alert(data);
            document.location.href = document.location.href;
        }
    });
    $(div).parent().html('Attended');
}
function absent(div, id, name) {
    if (!confirm('Are you sure ' + name + ' was absent from the class?')) {
        return;
    }
    $.get('/absent/' + id, function (data) {
        if (data != 'Success') {
            alert(data);
            // document.location.href=document.location.href;
        }
    });
    $(div).parent().html('Absent');
}

function validateEmail(email) {
    var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    return re.test(email);
}