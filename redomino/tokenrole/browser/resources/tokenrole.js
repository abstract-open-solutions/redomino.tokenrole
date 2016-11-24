token = $.cookie('token').replace(/"/g,'').split('|');
if (token.length == 2){
    path = atob(token[1])
    if (path && window.location.pathname.substring(0, path.length) == path){
        $('#portal-breadcrumbs a[href*='+path+']').each(function(){
            href = $(this).attr('href');
            $(this).attr('href', href + '/private_token_listing');
        });
    }
}
