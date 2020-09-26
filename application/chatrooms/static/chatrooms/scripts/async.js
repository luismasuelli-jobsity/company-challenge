(function($){
    $.fn.serializeObject = $.fn.serializeObject || function()  {
        let o = {};
        let a = this.serializeArray();
        $.each(a, function() {
            if (o[this.name]) {
                if (!o[this.name].push) {
                    o[this.name] = [o[this.name]];
                }
                o[this.name].push(this.value || '');
            } else {
                o[this.name] = this.value || '';
            }
        });
        return o;
    };

    function getFunction(func) {
        if (func) {
            if (typeof func === 'string') {
                func = window[func];
            }
            if (typeof func !== 'function') {
                func = function(baseObj) { return baseObj; };
            }
        } else {
            func = function(baseObj) { return baseObj; };
        }
        return func;
    }

    $(function(){
        $(document).on('submit', 'form.asynchronous', function() {
            let form = this;
            let $form = $(form);

            let method = ($form.attr('method') || 'get').toLowerCase();
            let action = ($form.attr('action') || '');
            let enctype = ($form.attr('enctype') || '').toLowerCase().trim();

            // custom settings may be added if attribute data-customizer="foo" exists,
            //   and window.foo() can be called.
            let extra = getFunction($form.data('extra'));

            // enctype may be: multipart/form-data, application/x-www-form-urlencoded, text/plain, application/json
            let data;
            switch(enctype) {
                case 'application/json':
                    data = JSON.stringify(extra($form.serializeObject()));
                    break;
                case 'multipart/form-data':
                    data = new FormData(extra(form));
                    break;
                //case 'application/x-www-form-urlencoded':
                //case 'text/plain':
                default:
                    data = extra($form.serialize());
            }

            if (['application/json', 'multipart/form-data', 'text/plain',
                'application/x-www-form-urlencoded'].indexOf(enctype) < 0) {
                enctype = 'application/x-www-form-urlencoded';
            }

            // custom settings may be added if attribute data-customizer="foo" exists,
            //   and window.foo() can be called.
            let customizer = getFunction($form.data('customizer'));

            let submitting = false;
            if (!submitting) {
                submitting = true;
                let settings = customizer({
                    contentType: enctype,
                    url: action,
                    method: method,
                    data: data,
                    success: function(data, statusText, xhr) { $form.trigger('async:success', [data, statusText, xhr]); },
                    error: function(xhr, statusText, errorText) { $form.trigger('async:error', [xhr, statusText, errorText]) },
                    complete: function(xhr, statusText) {
                        submitting = false;
                        $form.trigger('async:complete', [xhr, statusText]);
                    }
                });
                $.ajax(settings);
            }
            return false;
        })
    });
})(jQuery);