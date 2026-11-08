export default {fetch(request){const u=new URL(request.url);u.hostname='mntrplus.com';return Response.redirect(u.toString(),301)}}
