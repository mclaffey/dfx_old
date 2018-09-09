function flashAnnotateMessage(msg) {
	msg_div = $('<div class="blurb-message">' + msg + '</div>');
	$("#blurb-message-holder").append(msg_div);
	msg_div.delay(3000).fadeOut(); 
};

function prepareBlurbs(url_prefix, blurbable_selector) {

	// Add message
	$('body').prepend( $('<div id="blurb-message-holder"></div>') );

	// Add a blurb it button to each section
	$(blurbable_selector).each(function(){
	    $(this).prepend('<div class="blurb-button">Blurb it</div>');
	});

	// When hovering over blurb button, highlight button and section
	$('.blurb-button').hover(
		function(){
			$(this).parent().addClass("blurbable-hover");
		},
		function(){
			$(this).parent().removeClass("blurbable-hover");
	  }
	);

	// Add AJAX functionality to each blurb it button
	$('.blurb-button').bind('click', function() {
		// get the parent of the blurb it button, which is the blurbable div, and return the blurbable's immediate content
		// https://stackoverflow.com/questions/3442394/using-text-to-retrieve-only-text-not-nested-in-child-tags
		// content = $(this).parent().contents().filter(function(){ return this.nodeType == 3; })[0].nodeValue
		content = $(this).parent().clone();
		content.children(".blurb-button").remove();
/*		content = content.html();
		$.getJSON(url_prefix + '/annotate/add_to_current', {
			content: content
		}, function(resp) {
			flashAnnotateMessage('Created <a href="/annotate/view/' + resp.new_blurb + '">' + resp.new_blurb + 
				'</a> on <a href="/annotate/view/' + resp.parent_blurb + '">' + resp.parent_blurb + '</a>');
	    })
	    	.fail(function(jqXHR, textStatus, errorThrown)  {
	    		flashAnnotateMessage('Failed to blurb' + textStatus);
	    	});
*/    	$.post(url_prefix + '/annotate/add_to_current', {content: content.html()}, function(responseData) {
    		flashAnnotateMessage(responseData['message']);
    		});


	  	return false;
	});
};